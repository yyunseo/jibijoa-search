from types import SimpleNamespace

from tests.fakes.embeddings import _vec
from tests.fakes.qdrant import FakePoint
from tests.targets import sym

_PANELS = [
    # panel_id, gender, birth_year, region_major, region_minor, job, smoking, car, income, family_size, children
    ("p01", "남성", 2001, "서울", "강남구", "사무직", ["일반 담배"], "있음", "월 300~399만원", "1인 가구", 0),
    ("p02", "여성", 1999, "서울", "마포구", "전문직", "피우지 않음", "없음", "월 400~499만원", "2명", 0),
    ("p03", "남성", 1998, "경기", "수원시", "기술직", ["전자 담배"], "있음", "월 500~599만원", "3명", 1),
    ("p04", "여성", 1985, "부산", "해운대구", "서비스직", "피우지 않음", "있음", "월 200~299만원", "4명 이상", 2),
    ("p05", "남성", 1975, "서울", "송파구", "경영관리직", ["일반 담배"], "있음", "월 700만원 이상", "3명", 1),
    ("p06", "여성", 2002, "경기", "성남시", "학생", "피우지 않음", "없음", "월 100만원 미만", "1인 가구", 0),
    ("p07", "남성", 1996, "인천", "연수구", "판매직", "피우지 않음", "있음", "월 300~399만원", "2명", 0),
    ("p08", "여성", 1990, "서울", "종로구", "사무직", ["궐련형 전자담배"], "없음", "월 300~399만원", "1인 가구", 0),
]

_OTT = ["2개", "3개", "1개", "이용 안 함", "4개", "1개", "없음", "2개"]
_STRESS = ["운동", "잠", "음악 감상", "운동", "산책", "딱히 없음", "게임", "운동"]
_PET = ["반려동물을 키우고 있다", "키워본 적이 없다", "예전에 키운 적이 있다", "키워본 적이 없다",
        "반려동물을 키우고 있다", "키워본 적이 없다", "반려동물을 키우고 있다", "예전에 키운 적이 있다"]
_HOBBY = ["주말마다 넷플릭스를 본다", "등산을 즐긴다", "게임을 자주 한다", "요리를 좋아한다",
          "골프를 친다", "웹툰을 본다", "축구를 한다", "OTT로 드라마를 본다"]


def build_dataset() -> SimpleNamespace:
    q = sym("QPOLL_FIELD_TO_TEXT")
    panels = {}
    for pid, g, by, rmaj, rmin, job, smoke, car, inc, fam, kids in _PANELS:
        panels[pid] = {
            "panel_id": pid, "gender": g, "birth_year": by, "region_major": rmaj, "region_minor": rmin,
            "job_title_raw": job, "smoking_experience": smoke, "car_ownership": car,
            "income_household_monthly": inc, "income_personal_monthly": inc,
            "family_size": fam, "children_count": kids, "marital_status": "미혼" if kids == 0 else "기혼",
            "education_level": "대학교 졸업",
        }

    qpoll, welcome = [], []
    pid_list = [p[0] for p in _PANELS]
    point_id = 1
    for i, pid in enumerate(pid_list):
        rows = [
            ("ott_count", f"현재 OTT서비스를 {_OTT[i]} 이용 중이다."),
            ("stress_relief_method", f"스트레스를 해소하는데 주로 사용하는 방법은 {_STRESS[i]}이다."),
            ("pet_experience", f"{_PET[i]}."),
        ]
        for field, sentence in rows:
            payload = {"panel_id": pid, "question": q[field], "sentence": sentence}
            qpoll.append(FakePoint(point_id, payload, _vec(sentence)))
            point_id += 1
        text = _HOBBY[i]
        welcome.append(FakePoint(point_id, {"page_content": text, "metadata": {"panel_id": pid}}, _vec(text)))
        point_id += 1

    return SimpleNamespace(
        panels=panels,
        collections={"qpoll_vectors_v2": qpoll, "welcome_subjective_vectors": welcome},
    )
