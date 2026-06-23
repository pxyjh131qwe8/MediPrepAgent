# 先开发规则服务，科室推荐功能开发，先独立实现，后面agent再调用他

# 后续优化：可以引入更复杂的规则引擎，或者使用机器学习模型来进行科室推荐

from collections import defaultdict
from app.models.schemas import DepartmentResult


class DepartmentService:
    """科室推荐服务"""
    
    DEPARTMENT_RULES = {
        "头痛": {
            "departments": ["神经内科", "全科医学科"],
            "weight": 3
        },

        "失眠": {
            "departments": ["睡眠医学科", "精神心理科"],
            "weight": 2
        },

        "胸痛": {
            "departments": ["心内科", "急诊科"],
            "weight": 5
        },

        "咳嗽": {
            "departments": ["呼吸内科"],
            "weight": 3
        },

        "胃痛": {
            "departments": ["消化内科"],
            "weight": 3
        },

        "焦虑": {
            "departments": ["精神心理科"],
            "weight": 2
        }
    }
    
    def recommend_department(self, symptoms: str) -> DepartmentResult:
        """规则化根据症状推荐科室"""
        department_scores = defaultdict(int) 
        
        matched_symptoms = [] 
        
        # 寻找匹配的症状并累加科室分数
        for symptom, rule in self.DEPARTMENT_RULES.items():
            if symptom in symptoms: 
                matched_symptoms.append(symptom) 
                for dept in rule["departments"]:
                    department_scores[dept] += rule["weight"]
        
        # 如果没有匹配到任何症状，默认推荐全科医学科
        if not department_scores: 
            return DepartmentResult(
                primary_department="全科医学科",
                alternative_departments=["全科医学科"],
                reason="未匹配到特定症状，推荐全科医学科"
            ) 
        
        # 根据分数排序推荐科室
        sorted_departments = sorted(
            department_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        ) 
        
        primary = sorted_departments[0][0]  
        
        # 备选科室全局去重
        seen = set() 
        alternatives = []
        for dept, score in sorted_departments[1:]:
            if dept != primary and dept not in seen:
                alternatives.append(dept)
                seen.add(dept)
        
        return DepartmentResult(
            primary_department=primary,
            alternative_departments=alternatives,
            reason=f"检测到症状: {', '.join(matched_symptoms)}"
        )          
    
    

















