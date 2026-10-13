import datetime


def calculate_age_from_birth_year(birth_year, current_year: int = None) -> int:
    """출생연도로부터 나이 계산 (현재 연도 동적 적용)"""
    if current_year is None:
        current_year = datetime.datetime.now().year
        
    try:
        return current_year - int(birth_year)
    except:
        return 0


def get_age_group(birth_year) -> str:
    """출생연도로부터 연령대 반환"""
    age = calculate_age_from_birth_year(birth_year)
    if age < 20: return "10대"
    elif age < 30: return "20대"
    elif age < 40: return "30대"
    elif age < 50: return "40대"
    elif age < 60: return "50대"
    else: return "60대 이상"
