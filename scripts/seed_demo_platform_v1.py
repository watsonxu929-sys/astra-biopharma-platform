"""Seed demo data for v0.6 Platform MVP. Idempotent. Requires --run flag to execute."""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_db
from app.models import Organization, Person
from app.models_platform import (
    IndustryTag, PersonTag, PersonProfile, Favorite, Follow, ContactIntent,
    IntelligenceItem, MarketResource, CooperationOpportunity,
    FollowUp, CollabTask, TimelineEntry,
)
from app.services.platform_service import seed_default_tags
from sqlalchemy import select, func, text, delete


DEMO_MARKER = "[DEMO]"

# ── Demo data definitions ──

DEMO_ORGANIZATIONS = [
    {"standard_name": "明德生物医药有限公司", "org_type": "企业", "region": "上海", "industry_tags": "创新药;生物药"},
    {"standard_name": "华瑞医疗器械集团", "org_type": "企业", "region": "深圳", "industry_tags": "医疗器械;诊断"},
    {"standard_name": "东升制药股份有限公司", "org_type": "企业", "region": "北京", "industry_tags": "化学药;中药"},
    {"standard_name": "启明创投", "org_type": "投资机构", "region": "上海", "industry_tags": "产业投资;创新药"},
    {"standard_name": "苏州生物医药产业园", "org_type": "园区", "region": "苏州", "industry_tags": "园区与招商;生物药"},
    {"standard_name": "华东理工大学生物工程学院", "org_type": "高校", "region": "上海", "industry_tags": "科研服务;合成生物"},
    {"standard_name": "京华精准医学检测中心", "org_type": "企业", "region": "北京", "industry_tags": "诊断;基因与细胞治疗"},
    {"standard_name": "凯达CRO服务有限公司", "org_type": "企业", "region": "上海", "industry_tags": "CRO服务;临床研究"},
    {"standard_name": "新源CDMO有限公司", "org_type": "企业", "region": "杭州", "industry_tags": "CDMO服务;生物药"},
    {"standard_name": "科创实验室工程有限公司", "org_type": "企业", "region": "广州", "industry_tags": "实验室建设;仪器与耗材"},
]

DEMO_PEOPLE = [
    {"name": "张明远", "public_role": "创始人兼CEO", "organization_network": "明德生物医药有限公司", "ability_tags": "药物发现;临床研究"},
    {"name": "李思涵", "public_role": "首席科学家", "organization_network": "明德生物医药有限公司", "ability_tags": "生物药研发;质量管理"},
    {"name": "王建国", "public_role": "研发副总裁", "organization_network": "华瑞医疗器械集团", "ability_tags": "医疗器械研发;注册申报"},
    {"name": "陈小雪", "public_role": "市场总监", "organization_network": "华瑞医疗器械集团", "ability_tags": "市场准入;销售渠道"},
    {"name": "赵志强", "public_role": "总经理", "organization_network": "东升制药股份有限公司", "ability_tags": "生产工艺;质量管理"},
    {"name": "刘芳菲", "public_role": "BD总监", "organization_network": "东升制药股份有限公司", "ability_tags": "商务拓展;政府事务"},
    {"name": "周明辉", "public_role": "合伙人", "organization_network": "启明创投", "ability_tags": "投融资;行业研究"},
    {"name": "吴晓燕", "public_role": "投资经理", "organization_network": "启明创投", "ability_tags": "投融资;临床研究"},
    {"name": "郑建国", "public_role": "招商总监", "organization_network": "苏州生物医药产业园", "ability_tags": "园区招商;政府事务"},
    {"name": "孙教授", "public_role": "教授", "organization_network": "华东理工大学生物工程学院", "ability_tags": "合成生物;药物发现"},
    {"name": "钱一鸣", "public_role": "检测中心主任", "organization_network": "京华精准医学检测中心", "ability_tags": "诊断;基因与细胞治疗"},
    {"name": "韩雪梅", "public_role": "CRO事业部总经理", "organization_network": "凯达CRO服务有限公司", "ability_tags": "临床研究;注册申报"},
    {"name": "杨磊", "public_role": "工艺开发总监", "organization_network": "新源CDMO有限公司", "ability_tags": "生产工艺;生物药研发"},
    {"name": "朱敏", "public_role": "实验室设计主管", "organization_network": "科创实验室工程有限公司", "ability_tags": "实验室建设;仪器应用"},
    {"name": "黄晓峰", "public_role": "独立顾问", "organization_network": "", "ability_tags": "行业研究;投融资"},
    {"name": "林芳华", "public_role": "注册事务负责人", "organization_network": "明德生物医药有限公司", "ability_tags": "注册申报;质量管理"},
    {"name": "何大为", "public_role": "销售总监", "organization_network": "华瑞医疗器械集团", "ability_tags": "销售渠道;市场准入"},
    {"name": "沈洁", "public_role": "研发科学家", "organization_network": "华东理工大学生物工程学院", "ability_tags": "AI制药;药物发现"},
    {"name": "陆志远", "public_role": "投资总监", "organization_network": "启明创投", "ability_tags": "投融资;医疗器械"},
    {"name": "蔡明华", "public_role": "副院长", "organization_network": "京华精准医学检测中心", "ability_tags": "诊断;医疗服务"},
]

INTEL_TYPES = ["政策", "企业动态", "融资事件", "技术进展", "临床进展", "注册审批", "市场与销售", "人事动态", "行业研究"]

DEMO_INTELLIGENCE = [
    {"title": "CDE发布2026年创新药审评审批改革新规", "intel_type": "政策", "importance": 5, "credibility": 5,
     "summary": "国家药品监督管理局药品审评中心发布最新创新药审评审批改革方案，涉及突破性治疗药物、附条件批准等多项制度优化。",
     "industry_directions": "创新药;生物药;化学药", "source_name": "国家药监局"},
    {"title": "明德生物完成A+轮融资3亿元", "intel_type": "融资事件", "importance": 4, "credibility": 4,
     "summary": "明德生物医药有限公司宣布完成A+轮融资3亿元人民币，由启明创投领投，资金将用于核心管线临床推进。",
     "companies": "明德生物医药有限公司", "industry_directions": "创新药;生物药", "source_name": "动脉网"},
    {"title": "华瑞医疗新一代影像设备获NMPA批准", "intel_type": "注册审批", "importance": 4, "credibility": 5,
     "summary": "华瑞医疗器械集团新一代高清内窥镜影像系统获得国家药品监督管理局批准上市。",
     "companies": "华瑞医疗器械集团", "industry_directions": "医疗器械", "source_name": "NMPA"},
    {"title": "合成生物学产业发展白皮书2026发布", "intel_type": "行业研究", "importance": 3, "credibility": 4,
     "summary": "白皮书指出合成生物学在医药健康领域应用规模预计2028年突破500亿元。",
     "industry_directions": "合成生物", "source_name": "中国生物工程学会"},
    {"title": "苏州生物医药产业园引进3家创新药企业", "intel_type": "园区招商", "importance": 3, "credibility": 4,
     "summary": "苏州生物医药产业园与3家创新药企业签署入驻协议，涵盖细胞治疗、基因编辑等前沿领域。",
     "companies": "苏州生物医药产业园", "industry_directions": "园区与招商;创新药", "source_name": "苏州日报"},
    {"title": "基因治疗领域获新一轮政策支持", "intel_type": "政策", "importance": 4, "credibility": 4,
     "summary": "国务院办公厅发布关于促进基因与细胞治疗产业高质量发展的指导意见。",
     "industry_directions": "基因与细胞治疗", "source_name": "国务院办公厅"},
    {"title": "AI制药公司深势科技完成B轮融资", "intel_type": "融资事件", "importance": 3, "credibility": 4,
     "summary": "AI制药企业获得数亿元B轮融资，加速AI驱动药物研发平台建设。",
     "industry_directions": "AI制药;创新药", "source_name": "36氪"},
    {"title": "中药现代化取得重大突破", "intel_type": "技术进展", "importance": 3, "credibility": 3,
     "summary": "多个中药大品种完成循证医学研究，获得国际学术界认可。",
     "industry_directions": "中药", "source_name": "中国中医药报"},
    {"title": "2026中国医疗器械创新峰会即将召开", "intel_type": "会议活动", "importance": 2, "credibility": 4,
     "summary": "峰会将于10月在深圳举办，聚焦高端医疗器械国产替代和全球化路径。",
     "industry_directions": "医疗器械", "source_name": "医疗器械行业协会"},
    {"title": "生物制药CDMO产能持续扩张", "intel_type": "企业动态", "importance": 3, "credibility": 4,
     "summary": "国内多家CDMO企业宣布新建或扩建生产基地，满足不断增长的生物药生产需求。",
     "industry_directions": "CDMO服务;生物药", "source_name": "医药经济报"},
    {"title": "诊断试剂集采扩大范围", "intel_type": "政策", "importance": 4, "credibility": 5,
     "summary": "国家医保局发布通知，将体外诊断试剂集中带量采购范围扩大至更多品类。",
     "industry_directions": "诊断;医疗器械", "source_name": "国家医保局"},
    {"title": "创新药企出海策略研讨会成功举办", "intel_type": "会议活动", "importance": 2, "credibility": 3,
     "summary": "研讨会上多位专家分享了中国创新药企出海的经验和策略。",
     "industry_directions": "创新药", "source_name": "同写意"},
    {"title": "细胞治疗商业化进程加速", "intel_type": "市场与销售", "importance": 4, "credibility": 3,
     "summary": "国内首款CAR-T产品2026年上半年销售额突破5亿元，细胞治疗商业化前景广阔。",
     "industry_directions": "基因与细胞治疗", "source_name": "医药魔方"},
    {"title": "医疗器械注册人制度进一步改革", "intel_type": "政策", "importance": 3, "credibility": 4,
     "summary": "国家药监局发布医疗器械注册人制度深化改革方案，简化注册流程。",
     "industry_directions": "医疗器械;注册审批", "source_name": "国家药监局"},
    {"title": "华东理工大学发现新型抗菌肽", "intel_type": "技术进展", "importance": 3, "credibility": 4,
     "summary": "华东理工大学生物工程学院团队在Nature Communications发表新型抗菌肽研究成果。",
     "companies": "华东理工大学生物工程学院", "industry_directions": "科研服务", "source_name": "Nature Communications"},
    {"title": "实验室建设标准更新", "intel_type": "政策", "importance": 2, "credibility": 5,
     "summary": "住房和城乡建设部发布新版生物安全实验室建筑技术标准。",
     "industry_directions": "实验室建设", "source_name": "住建部"},
    {"title": "京华精准医学中心与多家药企达成战略合作", "intel_type": "企业动态", "importance": 3, "credibility": 3,
     "summary": "京华精准医学检测中心宣布与5家创新药企签署伴随诊断合作协议。",
     "companies": "京华精准医学检测中心", "industry_directions": "诊断;创新药", "source_name": "企业公告"},
    {"title": "2026上半年医药行业投融资回顾", "intel_type": "行业研究", "importance": 4, "credibility": 4,
     "summary": "2026年上半年中国医药健康领域共完成融资交易386起，总金额约1200亿元。",
     "industry_directions": "产业投资", "source_name": "清科研究"},
    {"title": "凯达CRO获得FDA GLP认证", "intel_type": "注册审批", "importance": 4, "credibility": 5,
     "summary": "凯达CRO服务有限公司药物安全评价中心通过美国FDA GLP检查。",
     "companies": "凯达CRO服务有限公司", "industry_directions": "CRO服务;临床研究", "source_name": "凯达CRO官网"},
    {"title": "创新医疗器械特别审批目录更新", "intel_type": "注册审批", "importance": 4, "credibility": 5,
     "summary": "国家药监局发布2026年第二批创新医疗器械特别审批目录，共18个产品入选。",
     "industry_directions": "医疗器械;创新药", "source_name": "NMPA"},
]

DEMO_RESOURCES = [
    {"title": "创新药CMC工艺开发服务", "direction": "supply", "resource_type": "CRO服务",
     "summary": "提供从处方前研究到IND申报的一站式CMC开发服务，涵盖小分子和生物药。", "industry_direction": "创新药;生物药", "region": "上海"},
    {"title": "GMP级细胞培养基供应", "direction": "supply", "resource_type": "试剂耗材",
     "summary": "国产GMP级无血清细胞培养基，适用于CHO细胞、293细胞等表达系统。", "industry_direction": "生物药;基因与细胞治疗", "region": "苏州"},
    {"title": "实验室整体设计与施工服务", "direction": "supply", "resource_type": "实验室设计与工程",
     "summary": "提供BSL-2/BSL-3实验室整体设计、施工和认证一站式服务。", "industry_direction": "实验室建设", "region": "全国"},
    {"title": "融资顾问服务", "direction": "supply", "resource_type": "融资资源",
     "summary": "专注生物医药领域，提供A轮-B轮融资顾问服务，历史成功案例30+。", "industry_direction": "产业投资;创新药", "region": "北京;上海"},
    {"title": "医疗器械注册全程服务", "direction": "supply", "resource_type": "注册服务",
     "summary": "提供医疗器械NMPA注册、CE认证、FDA 510(k)全流程服务。", "industry_direction": "医疗器械", "region": "全国"},
    {"title": "AI辅助药物设计平台", "direction": "supply", "resource_type": "技术成果",
     "summary": "基于深度学习的分子生成和优化平台，支持多靶点药物设计。", "industry_direction": "AI制药;创新药", "region": "线上"},
    {"title": "生物安全柜及洁净设备供应", "direction": "supply", "resource_type": "仪器设备",
     "summary": "国产品牌生物安全柜、超净工作台、洁净室设备，性价比高。", "industry_direction": "仪器与耗材;实验室建设", "region": "广州"},
    {"title": "临床CRO服务-肿瘤领域", "direction": "supply", "resource_type": "CRO服务",
     "summary": "专注肿瘤领域I-III期临床研究，团队经验丰富。", "industry_direction": "临床研究;创新药", "region": "上海"},
    {"title": "寻找ADC药物合作开发伙伴", "direction": "demand", "resource_type": "技术成果",
     "summary": "拥有ADC payload-linker技术平台，寻找具有抗体开发能力的合作伙伴。", "industry_direction": "创新药;生物药", "region": "深圳"},
    {"title": "寻找B轮融资", "direction": "demand", "resource_type": "融资资源",
     "summary": "小分子创新药企业，核心管线进入临床II期，寻找5000万-1亿元B轮融资。", "industry_direction": "创新药;化学药", "region": "上海"},
    {"title": "寻找生物药CDMO合作伙伴", "direction": "demand", "resource_type": "CDMO服务",
     "summary": "需要2000L规模CHO细胞培养和纯化CDMO服务，满足中美双报要求。", "industry_direction": "生物药;CDMO服务", "region": "长三角"},
    {"title": "寻找医疗器械海外注册代理商", "direction": "demand", "resource_type": "销售代理",
     "summary": "国产高端影像设备寻求东南亚和南美地区代理商合作。", "industry_direction": "医疗器械", "region": "海外"},
    {"title": "园区招商-生物医药企业", "direction": "supply", "resource_type": "园区载体",
     "summary": "苏州生物医药产业园提供GMP标准厂房、研发实验室和孵化空间。", "industry_direction": "园区与招商;生物药", "region": "苏州"},
    {"title": "寻找创新药license-in项目", "direction": "demand", "resource_type": "投资项目",
     "summary": "国内上市药企寻找临床II期以后的创新药license-in机会。", "industry_direction": "创新药;化学药", "region": "全国"},
    {"title": "高端人才猎头服务", "direction": "supply", "resource_type": "人才与职位",
     "summary": "专注生物医药行业CXO和研发VP级别人才猎聘服务。", "industry_direction": "创新药;生物药", "region": "全国"},
    {"title": "寻找检测方法开发合作伙伴", "direction": "demand", "resource_type": "检测服务",
     "summary": "细胞治疗企业需要流式细胞术和PCR方法学开发和验证服务。", "industry_direction": "基因与细胞治疗;检测服务", "region": "北京"},
    {"title": "化学合成定制服务", "direction": "supply", "resource_type": "CRO服务",
     "summary": "提供从mg到kg级的化学合成定制服务，快速交付。", "industry_direction": "化学药;创新药", "region": "上海"},
    {"title": "寻找GMP车间设计施工单位", "direction": "demand", "resource_type": "实验室设计与工程",
     "summary": "新建生物药GMP车间，需符合中国GMP和EU GMP标准。", "industry_direction": "生物药;实验室建设", "region": "杭州"},
    {"title": "进口分析仪器代理销售", "direction": "supply", "resource_type": "仪器设备",
     "summary": "代理销售国际知名品牌液相色谱、质谱等分析仪器。", "industry_direction": "仪器与耗材;研发服务", "region": "全国"},
    {"title": "寻找中药质量标准研究合作方", "direction": "demand", "resource_type": "检测服务",
     "summary": "需要中药指纹图谱和含量测定方法建立及验证服务。", "industry_direction": "中药;检测服务", "region": "北京"},
]

DEMO_OPPORTUNITIES = [
    {"title": "明德生物与凯达CRO临床合作", "opp_type": "服务采购", "stage": "negotiating",
     "description": "明德生物委托凯达CRO开展核心管线临床I期研究。"},
    {"title": "华瑞医疗东南亚市场拓展", "opp_type": "渠道合作", "stage": "contacted",
     "description": "寻找东南亚代理商，拓展医疗器械海外市场。"},
    {"title": "东升制药license-in评估", "opp_type": "技术合作", "stage": "due_diligence",
     "description": "评估从海外引进两个临床II期小分子新药项目。"},
    {"title": "启明创投考察基因治疗项目", "opp_type": "投融资", "stage": "qualified",
     "description": "对一家基因治疗初创企业进行投资尽调。"},
    {"title": "苏州园区优惠政策对接", "opp_type": "园区落地", "stage": "contacted",
     "description": "协助两家有意落户的创新药企业对接园区扶持政策。"},
    {"title": "京华精准医学与药企伴随诊断合作", "opp_type": "技术合作", "stage": "proposal",
     "description": "为某创新药企业开发配套伴随诊断试剂。"},
    {"title": "华东理工大学生物技术成果转化", "opp_type": "技术合作", "stage": "lead",
     "description": "推动合成生物学实验室成果向产业转化。"},
    {"title": "科创实验室参加医院改造项目", "opp_type": "项目合作", "stage": "agreement",
     "description": "为两家三甲医院提供实验室升级改造服务。"},
    {"title": "行业研究报告合作", "opp_type": "专家咨询", "stage": "won",
     "description": "多位产业专家合作完成生物医药产业发展白皮书。"},
    {"title": "医疗器械注册服务年度合作", "opp_type": "服务采购", "stage": "proposal",
     "description": "为华瑞医疗提供年度医疗器械注册代理服务。"},
]


def seed_demo_data():
    print("[DEMO] Seeding platform demo data...")
    db = next(get_db())

    try:
        # Seed tags first
        seed_default_tags(db)

        # Check existing demo data
        existing_orgs = db.scalar(select(func.count()).select_from(Organization).where(Organization.standard_name.like(f"%{DEMO_MARKER}%"))) or 0
        if existing_orgs > 0:
            print(f"[DEMO] Found {existing_orgs} existing demo orgs, skipping creation.")
            print("[DEMO] Demo data seeding skipped (already exists). Use --clean to remove first.")
            return

        # ── Create demo organizations ──
        tag_map = {t.tag_key: t.id for t in db.scalars(select(IndustryTag)).all()}
        created_orgs = {}
        for org_data in DEMO_ORGANIZATIONS:
            org = Organization(
                standard_name=f"{DEMO_MARKER} {org_data['standard_name']}",
                org_type=org_data["org_type"],
                region=org_data["region"],
                industry_tags=org_data["industry_tags"],
                visibility="内部",
                verification_status="已核验",
                source_type="演示数据",
                captured_at=datetime.now(),
            )
            from app.services.id_generator import assign_system_id
            assign_system_id(db, org, "organizations")
            db.add(org)
            db.flush()
            created_orgs[org_data["standard_name"]] = org

        # ── Create demo people ──
        from app.services.id_generator import assign_system_id
        created_people = {}
        for i, person_data in enumerate(DEMO_PEOPLE):
            person = Person(
                name=person_data["name"],
                public_role=person_data["public_role"],
                organization_network=person_data["organization_network"] if person_data["organization_network"] else None,
                ability_tags=person_data["ability_tags"],
                visibility="内部",
                verification_status="已核验",
                source_type="演示数据",
                captured_at=datetime.now(),
            )
            assign_system_id(db, person, "people")
            db.add(person)
            db.flush()
            created_people[person_data["name"]] = person

            # Create person profile
            profile = PersonProfile(
                person_id=person.id,
                title="研究员" if random.random() > 0.5 else "博士",
                bio=f"{person_data['name']}是{person_data['organization_network']}的{person_data['public_role']}，在生物医药产业有丰富经验。" if person_data['organization_network'] else f"{person_data['name']}是一位资深的产业人士。",
                province=random.choice(["上海", "北京", "深圳", "苏州", "杭州", "广州"]),
                cooperation_preferences=random.choice(["技术合作", "投融资", "人才合作", "市场合作"]),
                contact_visibility=random.choice(["connected", "members"]),
                is_demo=True,
            )
            db.add(profile)

            # Assign some tags
            all_tags = db.scalars(select(IndustryTag)).all()
            assigned = random.sample(all_tags, min(4, len(all_tags)))
            for tag in assigned:
                db.add(PersonTag(person_id=person.id, tag_id=tag.id))

        # ── Create demo intelligence items ──
        for intel_data in DEMO_INTELLIGENCE:
            item = IntelligenceItem(
                title=intel_data["title"],
                summary=intel_data["summary"],
                intel_type=intel_data["intel_type"],
                companies=intel_data.get("companies"),
                industry_directions=intel_data.get("industry_directions"),
                source_name=intel_data["source_name"],
                credibility=intel_data["credibility"],
                importance=intel_data["importance"],
                visibility="public",
                status="published",
                published_at=datetime.now() - timedelta(days=random.randint(0, 30)),
                is_demo=True,
            )
            db.add(item)

        # ── Create demo resources ──
        for res_data in DEMO_RESOURCES:
            resource = MarketResource(
                title=res_data["title"],
                direction=res_data["direction"],
                resource_type=res_data["resource_type"],
                summary=res_data["summary"],
                publisher_id=0,
                industry_direction=res_data["industry_direction"],
                region=res_data["region"],
                status="published",
                contact_visibility=random.choice(["connected", "members"]),
                is_demo=True,
            )
            db.add(resource)

        # ── Create demo opportunities ──
        for opp_data in DEMO_OPPORTUNITIES:
            opp = CooperationOpportunity(
                title=opp_data["title"],
                opp_type=opp_data["opp_type"],
                stage=opp_data["stage"],
                initiator_id=0,
                description=opp_data["description"],
                status="active",
                visibility="public",
                is_demo=True,
                source_type="manual",
            )
            db.add(opp)
            db.flush()

            # Add sample timeline entries
            stages = ["lead", "contacted", "qualified", "negotiating", "proposal"]
            for si, s in enumerate(stages[:stages.index(opp_data["stage"]) if opp_data["stage"] in stages else 1]):
                db.add(TimelineEntry(
                    opportunity_id=opp.id,
                    event_type="stage_change" if si > 0 else "created",
                    description=f"进入「{s}」阶段" if si > 0 else f"合作机会「{opp_data['title']}」已创建",
                    created_at=datetime.now() - timedelta(days=(len(stages) - si) * 7),
                ))

        db.commit()
        print(f"[DEMO] Seeded: {len(DEMO_ORGANIZATIONS)} orgs, {len(DEMO_PEOPLE)} people, {len(DEMO_INTELLIGENCE)} intelligence items, {len(DEMO_RESOURCES)} resources, {len(DEMO_OPPORTUNITIES)} opportunities.")

    except Exception as e:
        db.rollback()
        print(f"[DEMO] ERROR: {e}")
        raise
    finally:
        db.close()


def clean_demo_data():
    """Remove all demo-marked data."""
    print("[DEMO] Cleaning demo data...")
    db = next(get_db())
    try:
        tables = [
            ("v06_timeline_entries", "opportunity_id IN (SELECT id FROM v06_opportunities WHERE is_demo=1)"),
            ("v06_follow_ups", "opportunity_id IN (SELECT id FROM v06_opportunities WHERE is_demo=1)"),
            ("v06_collab_tasks", "is_demo=1"),
            ("v06_opportunities", "is_demo=1"),
            ("v06_market_resources", "is_demo=1"),
            ("v06_intelligence_items", "is_demo=1"),
            ("v06_intel_subscriptions", "1=1"),
            ("v06_favorites", "1=1"),
            ("v06_follows", "1=1"),
            ("v06_contact_intents", "1=1"),
            ("v06_person_profiles", "is_demo=1"),
            ("v06_person_tags", "person_id IN (SELECT id FROM people WHERE source_type='演示数据')"),
            ("v06_organization_tags", "1=1"),
            ("people", "source_type='演示数据'"),
            ("organizations", "source_type='演示数据'"),
        ]
        for table, condition in tables:
            result = db.execute(text(f"DELETE FROM {table} WHERE {condition}"))
            print(f"[DEMO] Cleaned {table}: {result.rowcount} rows")
        db.commit()
        print("[DEMO] Demo data cleaned successfully.")
    except Exception as e:
        db.rollback()
        print(f"[DEMO] ERROR cleaning: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean_demo_data()
    elif "--run" in sys.argv:
        seed_demo_data()
    else:
        print("Usage:")
        print("  python scripts/seed_demo_platform_v1.py --run    # Seed demo data")
        print("  python scripts/seed_demo_platform_v1.py --clean  # Clean demo data")
        print("NOTE: Requires --run or --clean flag to execute.")
