import re
from typing import List, Dict, Union, Tuple, Optional, Any
import logging
from functools import lru_cache














# 2. 동적 부정어 관리 로직 (Logic)
COMMON_NEGATIVE_PATTERNS = [
    r"해\s*당\s*사\s*항\s*없\s*음",
    r"경\s*험\s*없\s*음",
    r"관\s*심\s*없\s*음",
    r"잘\s*모\s*름", r"모\s*르\s*겠", r"몰\s*라",
    r"딱\s*히\s*없",
    r"^없\s*음$", r"^없\s*다$", 
    r"^아\s*니\s*오$", r"^아\s*님$",
    r"^0$", r"^0개$", r"^0명$", r"^0원$"
]

SPECIFIC_NEGATIVE_PATTERNS = {
    "ott_count": [r"안\s*봄", r"보\s*지\s*않", r"이\s*용\s*하\s*지\s*않", r"이\s*용\s*안", r"구\s*독\s*안", r"없\s*음", r"0\s*개", r"^없\s*음$"],
    "smoking_experience": [r"안\s*피", r"피\s*우\s*지\s*않", r"비\s*흡\s*연", r"금\s*연", r"흡\s*연\s*안", r"없\s*음"],
    "drinking_experience": [r"안\s*마\s*심", r"마\s*시\s*지\s*않", r"비\s*음\s*주", r"금\s*주", r"없\s*음"],
    "pet_experience": [r"안\s*키\s*움", r"키\s*우\s*지\s*않", r"비\s*반\s*려", r"없\s*음", r"^없\s*음$"],
    "ai_chatbot_used": [r"안\s*써\s*봄", r"사\s*용\s*안", r"사\s*용\s*해\s*본\s*적\s*없", r"없\s*음", r"^없\s*음$"],
    
    "fast_delivery_usage": [
        r"^없\s*음$", 
        r"이\s*용\s*경\s*험\s*없",
        r"직\s*접\s*구\s*매",        
        r"직\s*접\s*장\s*을",        
        r"배\s*송\s*안\s*함",
        r"배\s*송\s*시\s*키\s*지\s*않",
        r"이\s*용.*안\s*함",  
        r"이\s*용.*하\s*지\s*않",
        r"사\s*용.*안\s*함",
        r"쓰\s*지\s*않",
        r"안\s*씀"
    ],

    "summer_worry": [r"걱\s*정\s*없", r"^없\s*다$", r"^없\s*음$"], 
    "moving_stress_factor": [r"스트레스\s*받\s*지", r"안\s*받", r"^없\s*다$"], 
    "stress_situation": [r"안\s*받\s*음", r"없\s*다$"],
    "sweat_discomfort": [r"불\s*편\s*함\s*없", r"딱\s*히", r"^없\s*음$"],
    "lunar_new_year_gift_pref": [r"선\s*호\s*하\s*는.*없", r"^없\s*음$"],
    "children_count": [r"자\s*녀\s*없\s*음", r"무\s*자\s*녀"],
    "stress_relief_method": [r"^없\s*음$", r"딱\s*히\s*없"],
}

def get_negative_patterns(field_name: str) -> List[str]:
    patterns = COMMON_NEGATIVE_PATTERNS.copy()
    if field_name in SPECIFIC_NEGATIVE_PATTERNS:
        patterns.extend(SPECIFIC_NEGATIVE_PATTERNS[field_name])
    return patterns


