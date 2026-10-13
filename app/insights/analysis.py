import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple


from app.panels.age import get_age_group
from app.panels.fields import (
    FIELD_ALIAS_MAP,
    FIELD_NAME_MAP,
    QPOLL_FIELD_TO_TEXT,
    VALUE_TRANSLATION_MAP,
    WELCOME_OBJECTIVE_FIELDS,
)
from app.panels.repository import PanelRepository
from app.query.field_matching import get_field_mapping
from app.query.router import get_router
from app.insights.charts import create_chart_data_optimized, create_crosstab_chart, create_qpoll_chart_data
from app.insights.distributions import (
    _clean_label,
    _sort_distribution,
    calculate_distribution,
    find_top_category,
)


def _analyze_fields_in_parallel(panels_data: List[Dict], candidate_fields: List[Tuple[str, str]]) -> List[Dict]:
    """병렬 필드 분석"""
    field_values = {fname: [] for fname, _ in candidate_fields}
    field_map = dict(candidate_fields)

    for item in panels_data:
        for fname in field_values.keys():
            val = item.get(fname)
            if val is None: continue

            if fname == "birth_year":
                field_values[fname].append(get_age_group(val))
            elif isinstance(val, list):
                for v in val:
                    cleaned = _clean_label(v)
                    if cleaned: field_values[fname].append(cleaned)
            else:
                cleaned = _clean_label(val)
                if cleaned: field_values[fname].append(cleaned)

    results = []
    for fname, vals in field_values.items():
        if not vals: continue
        try:
            dist = calculate_distribution(vals)
            final_dist = _sort_distribution(dist)
            if not final_dist: continue
            
            results.append({
                "field": fname,
                "korean_name": field_map[fname],
                "distribution": final_dist,
            })
        except: pass
    return results


def find_high_ratio_fields_optimized(
    panels_data: List[Dict], 
    exclude_fields: List[str], 
    threshold: float = 50.0,
    max_charts: int = 3
) -> List[Dict]:
    """높은 비율 필드 찾기 (98% 이상 제외)"""
    candidate_fields = []
    for fname, kname in WELCOME_OBJECTIVE_FIELDS:
        if fname not in exclude_fields:
            candidate_fields.append((fname, kname))
    
    if not candidate_fields: return []
    
    analysis_results = _analyze_fields_in_parallel(panels_data, candidate_fields)
    
    high_ratio_results = []
    for result in analysis_results:
        distribution = result['distribution']
        top_category, top_ratio = find_top_category(distribution)
        
        if top_ratio >= threshold:
            if top_ratio >= 98.0:
                continue

            high_ratio_results.append({
                "field": result['field'],
                "korean_name": result['korean_name'],
                "distribution": distribution,
                "top_category": top_category,
                "top_ratio": top_ratio
            })
    
    high_ratio_results.sort(key=lambda x: x["top_ratio"], reverse=True)
    return high_ratio_results[:max_charts]


def analyze_search_results_optimized(
    query: str,
    classified_keywords: dict,
    panel_id_list: List[str]
) -> Tuple[Dict, int]:
    logging.info(f"📊 분석 시작 (최적화) - panel_id 수: {len(panel_id_list)}개")
    
    if not panel_id_list:
        return {"main_summary": "검색 결과가 없습니다.", "charts": []}, 200
    
    try:
        panels_data = PanelRepository.fetch_panels_data(panel_id_list)

        if not panels_data: return {"main_summary": "데이터 없음", "charts": []}, 200
        fixed_filters = set()
        
        # 1. Demographic Filters 확인
        demographic_filters = classified_keywords.get('demographic_filters', {})
        if demographic_filters:
            for k, v in demographic_filters.items():
                if not isinstance(v, list) or len(v) == 1:
                    fixed_filters.add(k)
                    mapped_field = FIELD_ALIAS_MAP.get(k)
                    if mapped_field: fixed_filters.add(mapped_field)

        # 2. Structured Filters 확인
        structured_filters = classified_keywords.get('structured_filters', [])
        for f in structured_filters:
            if f.get('operator') in ['eq', 'like', 'ilike']: 
                 if f.get('field'): fixed_filters.add(f['field'])
    
        target_field = classified_keywords.get('target_field')
        
        if target_field:
            if target_field == 'job_duty_raw':
                logging.info(f"   🔄 대체 필드 적용: job_duty_raw -> job_title_raw")
                target_field = 'job_title_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'region_major':
                logging.info(f"   🔄 대체 필드 적용: region_major -> region_minor")
                target_field = 'region_minor'
                classified_keywords['target_field'] = target_field
            elif target_field in ['income_personal_monthly', 'income_household_monthly']:
                logging.info(f"   🔄 대체 필드 적용: {target_field} -> happiest_self_spending")
                target_field = 'happiest_self_spending' 
                classified_keywords['target_field'] = target_field
            elif target_field == 'car_ownership':
                logging.info(f"   🔄 대체 필드 적용: car_ownership -> car_model_raw")
                target_field = 'car_model_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'phone_brand_raw':
                logging.info(f"   🔄 대체 필드 적용: phone_brand_raw -> phone_model_raw")
                target_field = 'phone_model_raw'
                classified_keywords['target_field'] = target_field
            elif target_field == 'marital_status':
                logging.info(f"   🔄 대체 필드 적용: marital_status -> children_count")
                target_field = 'children_count'
                classified_keywords['target_field'] = target_field
            else:
                if target_field in fixed_filters:
                    logging.info(f"   🚫 '{target_field}'에 대한 대체 필드 없음 -> 타겟 해제하여 100% 차트 방지")
                    target_field = None 
                    classified_keywords['target_field'] = None

        
        raw_keywords = classified_keywords.get('ranked_keywords_raw', [])
        ranked_keywords = []
        search_used_fields = set()

        charts = []
        used_fields = [] 
        chart_tasks = []
        objective_fields = set([f[0] for f in WELCOME_OBJECTIVE_FIELDS])

        demographic_filters = classified_keywords.get('demographic_filters', {})
        if demographic_filters:
            if 'age_range' in demographic_filters: search_used_fields.add('birth_year')
            for key in demographic_filters: 
                if key != 'age_range': search_used_fields.add(key)

        if 'children_count' in demographic_filters or 'children_count' in search_used_fields:
            used_fields.append('marital_status')

        if 'region_major' in demographic_filters and 'region_minor' not in used_fields:
            logging.info("📍 지역 필터 감지 -> 세부 지역(region_minor) 분석 자동 추가")
            chart_tasks.append({
                "type": "filter",
                "kw_info": {
                    "field": "region_minor",
                    "description": "세부 지역 분포", 
                    "priority": 0 
                }
            })
            used_fields.append("region_minor")

        structured_filters = classified_keywords.get('structured_filters', [])
        for f in structured_filters:
            if f.get('field'): search_used_fields.add(f['field'])

        if raw_keywords:
            for i, kw in enumerate(raw_keywords):
                mapping = get_field_mapping(kw)
                ranked_keywords.append({
                    "keyword": kw, "field": mapping["field"], "description": mapping["description"],
                    "type": mapping.get("type", "unknown"), "priority": i + 10
                })
                if mapping.get("type") == 'filter' and mapping["field"] != 'unknown':
                    search_used_fields.add(mapping["field"])

        # 1. Main Target Field (0순위)
        if target_field and target_field != 'unknown' and target_field not in used_fields:
            if target_field in QPOLL_FIELD_TO_TEXT:
                chart_tasks.append({"type": "qpoll", "kw_info": {"field": target_field, "description": QPOLL_FIELD_TO_TEXT[target_field], "priority": 0}})
                used_fields.append(target_field)
            elif target_field in objective_fields:
                chart_tasks.append({"type": "filter", "kw_info": {"field": target_field, "description": FIELD_NAME_MAP.get(target_field, target_field), "priority": 0}})
                used_fields.append(target_field)

        # Q-Poll 타겟인 경우 기본 인구통계 자동 추가
        if target_field and target_field in QPOLL_FIELD_TO_TEXT:
            basic_demos = [('gender', '성별'), ('birth_year', '연령대'), ('region_major', '거주 지역')]
            for field, label in basic_demos:
                if field not in used_fields and field not in search_used_fields:
                    chart_tasks.append({
                        "type": "filter",
                        "kw_info": {"field": field, "description": label, "priority": 1}
                    })
                    used_fields.append(field)

        # 2. Semantic Conditions
        semantic_conditions = classified_keywords.get('semantic_conditions', [])
        for condition in semantic_conditions:
            original_keyword = condition.get('original_keyword')
            if not original_keyword: continue
            
            field_info = get_router().find_closest_field(original_keyword)
            if field_info:
                found_field = field_info['field']
                if found_field in used_fields: continue
                
                if found_field in fixed_filters:
                     continue

                logging.info(f"   💡 2차 의도 발견: '{original_keyword}' -> '{field_info['description']}' ({found_field})")
                
                if found_field in QPOLL_FIELD_TO_TEXT:
                    chart_tasks.append({"type": "qpoll", "kw_info": {"field": found_field, "description": QPOLL_FIELD_TO_TEXT[found_field], "priority": 1}})
                    used_fields.append(found_field)
                elif found_field in objective_fields:
                    chart_tasks.append({"type": "filter", "kw_info": {"field": found_field, "description": FIELD_NAME_MAP.get(found_field, found_field), "priority": 1}})
                    used_fields.append(found_field)

        # 3. 나머지 키워드
        for kw_info in ranked_keywords:
            if len(chart_tasks) >= 5: break
            field = kw_info.get('field', '')
            if field in used_fields: continue
            
            if field in fixed_filters:
                logging.info(f"🚫 키워드 차트 제외: '{field}'는 이미 필터로 고정됨")
                continue

            if kw_info.get('type') == 'qpoll':
                kw_info['priority'] = 2
                chart_tasks.append({"type": "qpoll", "kw_info": kw_info})
                used_fields.append(field)
            elif kw_info.get('type') == 'filter' and field not in search_used_fields:
                if field in objective_fields and field != 'unknown':
                    kw_info['priority'] = 2
                    chart_tasks.append({"type": "filter", "kw_info": kw_info})
                    used_fields.append(field)

        # 1인 가구 로직
        is_single_household = False
        fam_val = demographic_filters.get('family_size') or demographic_filters.get('household_size')
        if fam_val and (isinstance(fam_val, list) and any(str(v).startswith('1') for v in fam_val) or str(fam_val).startswith('1')): is_single_household = True
        if not is_single_household:
            for f in structured_filters:
                if f.get('field') in ['family_size', 'household_size']:
                    val = f.get('value')
                    if (isinstance(val, list) and any(str(v).startswith('1') for v in val) or str(val).startswith('1')): is_single_household = True
        if is_single_household: used_fields.append('income_household_monthly')

        # 차량 소유 비율 70% 이상 시 차종 차트 추가
        car_ownership_values = [p.get('car_ownership') for p in panels_data if p.get('car_ownership')]
        if car_ownership_values:
            flat_values = []
            car_map = VALUE_TRANSLATION_MAP.get('car_ownership', {}) 
            
            for v in car_ownership_values:
                if isinstance(v, list):
                    for sub_v in v:
                        cleaned = _clean_label(sub_v)
                        normalized = car_map.get(cleaned, cleaned)
                        flat_values.append(normalized)
                else:
                    cleaned = _clean_label(v)
                    normalized = car_map.get(cleaned, cleaned)
                    flat_values.append(normalized)
            
            car_dist = calculate_distribution(flat_values)
            if car_dist.get('있음', 0) >= 70.0:
                if 'car_model_raw' not in used_fields:
                    logging.info("🚗 차량 보유 비율 70% 이상 -> 차종(car_model_raw) 분석 자동 추가")
                    chart_tasks.append({
                        "type": "filter",
                        "kw_info": {
                            "field": "car_model_raw",
                            "description": "보유 차량 모델",
                            "priority": 1 
                        }
                    })
                    used_fields.append("car_model_raw")
                
                if 'car_ownership' not in used_fields:
                    used_fields.append("car_ownership")

        with ThreadPoolExecutor(max_workers=len(chart_tasks) or 1) as executor:
            futures = []
            for task in chart_tasks:
                kw = task['kw_info']
                if task['type'] == 'filter':
                    futures.append(executor.submit(create_chart_data_optimized, kw.get('keyword',''), kw.get('field'), kw.get('description'), panels_data))
                else:
                    futures.append(executor.submit(create_qpoll_chart_data, kw.get('field')))
                
                futures[-1].priority = kw.get('priority', 99)
            
            temp_results = []
            for future in as_completed(futures):
                try:
                    chart = future.result()
                    if chart.get('chart_data'):
                        temp_results.append((future.priority, chart))
                except: pass
            
            temp_results.sort(key=lambda x: x[0])
            charts.extend([res[1] for res in temp_results])

        # 교차 분석
        if len(charts) < 5:
            topic_info = None
            if target_field and target_field in used_fields:
                topic_info = {'field': target_field, 'description': QPOLL_FIELD_TO_TEXT.get(target_field, FIELD_NAME_MAP.get(target_field))}
            if not topic_info:
                for task in chart_tasks:
                    if task['type'] == 'qpoll':
                        topic_info = task['kw_info']
                        break
            
            if topic_info:
                t_field = topic_info['field']
                t_name = topic_info['description']
                axes = []
                standard_axes = [('birth_year','연령대'), ('gender','성별'), ('region_major','지역'), ('job_title_raw','직업')]
                for ax in standard_axes:
                    if ax[0] not in search_used_fields and ax[0] != t_field: axes.append(ax)
                for ax_field, ax_name in axes:
                    if len(charts) >= 5: break
                    crosstab = create_crosstab_chart(panels_data, ax_field, t_field, ax_name, t_name)
                    if crosstab and crosstab.get('chart_data'):
                        charts.append(crosstab)
                        used_fields.extend([ax_field, t_field])

        if len(charts) < 5:
            high_ratio = find_high_ratio_fields_optimized(panels_data, list(set(used_fields)|search_used_fields), max_charts=5-len(charts))
            for info in high_ratio:
                charts.append({"topic": f"{info['korean_name']} 분포", "description": f"{info['top_ratio']}%가 '{info['top_category']}'입니다.", "ratio": f"{info['top_ratio']}%", "chart_data": [{"label": info['korean_name'], "values": info['distribution']}]})

        return {
            "query": query, 
            "total_count": len(panels_data), 
            "main_summary": f"총 {len(panels_data)}명 데이터 분석 완료", 
            "charts": charts
        }, 200

    except Exception as e:
        logging.error(f"분석 중 오류: {e}", exc_info=True)
        return {"main_summary": "오류 발생", "charts": []}, 500
