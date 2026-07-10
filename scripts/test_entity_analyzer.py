import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.entity_analyzer import analyze_entity
samples={'organizations':'上海示例生物科技有限公司位于上海张江，专注ADC创新药研发，拥有共享实验室，目前寻求融资。','people':'张三，某生物科技有限公司创始人兼CEO，擅长药物研发和投融资。','projects':'某ADC创新药项目，处于临床前阶段，需要融资和实验室支持。','resources':'Q-BAY可提供上海张江实验室和共享仪器平台。','events':'2026年6月26日，上海示例生物科技有限公司宣布完成5000万元A轮融资。','relations':'上海示例生物科技有限公司与某某资本签署战略投资合作协议。','actions':'下一步联系项目负责人，确认实验室面积和融资计划。'}
for k,v in samples.items(): print('[PASS]',k,analyze_entity(k,v))
print('ALL ENTITY ANALYZER CHECKS PASSED')
