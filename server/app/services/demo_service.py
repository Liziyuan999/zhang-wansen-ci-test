# -*- coding: utf-8 -*-
"""演示模式：一键灌入演示数据 / 查询状态 / 一键清除（仅删演示标记数据，不碰真实数据）。

演示数据标记约定：
- 部门名以「[演示]」前缀；用户 email 以 demo_ 前缀；文档 file_hash 以 demo- 前缀
- LlmCallLog.scenario = "demo"；OperationLog.detail = "[demo-seed]"（检索热力图/部门活跃度可复用真实聚合，清除时精确隔离）
"""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    ConversationMsg,
    Department,
    DocChunk,
    Document,
    Entity,
    EntityRelation,
    LlmCallLog,
    OperationLog,
    SysConfig,
    User,
)

DEMO_DEPT_PREFIX = "[演示]"
DEMO_EMAIL_PREFIX = "demo_"
DEMO_HASH_PREFIX = "demo-"
DEMO_OP_MARK = "[demo-seed]"

# 演示文档内容（企业级质感，覆盖知识图谱/Agent/看板演示需求）
DEMO_DOCS: list[dict] = [
    {
        "doc_name": "新品上市企划案（演示）",
        "file_type": "pdf",
        "file_size": 2048000,
        "chunks": [
            "新品「智研 X1」智能办公终端将于下季度正式上市，定位企业级智慧办公入口，整合语音速记、会议纪要、知识问答三大核心场景。",
            "上市节奏分三阶段：预热期（第 1-2 周）发布白皮书并邀请头部客户内测；引爆期（第 3-4 周）联合渠道伙伴举办城市发布会；收割期（第 5-8 周）推出企业采购优惠方案并扩大直销团队。",
            "目标客户画像：员工规模 200-2000 人的成长型企业，重点关注知识密集型行业（咨询、金融、制造研发），核心决策人为 CIO 与行政负责人。",
            "销售目标：首季出货 3 万台、企业订阅收入 5000 万元；成功关键指标包括客户留存率 ≥ 85%、日均活跃率 ≥ 60%。",
        ],
    },
    {
        "doc_name": "研发效能白皮书（演示）",
        "file_type": "docx",
        "file_size": 1536000,
        "chunks": [
            "本白皮书总结研发效能改进三板斧：度量先行、自动化提效、知识沉淀。通过统一研发效能平台采集需求交付周期、缺陷密度、发布频率三大核心指标。",
            "自动化提效部分，重点建设 CI/CD 流水线与代码评审机器人，将发布前置时间从 3 天压缩到 6 小时，线上缺陷率下降 42%。",
            "知识沉淀体系由文档中心、代码知识库与智能问答构成，新人上手时间从 2 周缩短至 3 天，跨团队问题平均定位时长下降 60%。",
            "配套管理机制：每周效能看板复盘、季度 OKR 对齐，将效能数据纳入团队考核，形成持续改进飞轮。",
        ],
    },
    {
        "doc_name": "客户成功案例集（演示）",
        "file_type": "pdf",
        "file_size": 3072000,
        "chunks": [
            "某头部证券公司通过部署知寻 KnowSeek 构建投研知识中台，沉淀研报与合规文档 12 万份，检索准确率提升至 92%，研究员日均节省 1.5 小时。",
            "某连锁零售集团基于企业知识库搭建门店运营问答中心，将 SOP 培训周期从 4 周缩短至 5 天，客服一次解决率提升 18 个百分点。",
            "某智能制造企业利用知识图谱打通设备手册、故障案例与维修专家经验，故障平均定位时间由 2 小时降至 20 分钟，备件预测准确率提升 25%。",
        ],
    },
]

DEMO_ENTITIES: list[tuple[str, str]] = [
    ("智研 X1", "产品"),
    ("企业智慧办公", "方案"),
    ("CI/CD", "技术"),
    ("研发效能", "方案"),
    ("投研知识中台", "方案"),
    ("知寻 KnowSeek", "产品"),
]

DEMO_RELATIONS: list[tuple[str, str, str]] = [
    ("智研 X1", "企业智慧办公", "属于"),
    ("CI/CD", "研发效能", "支撑"),
    ("投研知识中台", "知寻 KnowSeek", "基于"),
    ("研发效能", "投研知识中台", "赋能"),
]


def _demo_departments(db: Session) -> list[Department]:
    names = ["[演示]市场部", "[演示]研发部"]
    depts = db.query(Department).filter(Department.dept_name.in_(names)).all()
    exist = {d.dept_name: d for d in depts}
    out = []
    for name in names:
        if name in exist:
            out.append(exist[name])
        else:
            d = Department(dept_name=name, description="演示模式自动生成的部门", sort_order=999)
            db.add(d)
            db.flush()
            out.append(d)
    return out


def _demo_users(db: Session, depts: list[Department]) -> list[User]:
    plan = [
        ("demo_market", "demo_market@knowseek.com", depts[0], "市场总监"),
        ("demo_rd", "demo_rd@knowseek.com", depts[1], "研发负责人"),
    ]
    users = db.query(User).filter(User.email.like(f"{DEMO_EMAIL_PREFIX}%")).all()
    exist = {u.email: u for u in users}
    out = []
    for username, email, dept, _label in plan:
        if email in exist:
            out.append(exist[email])
            continue
        u = User(
            username=username,
            email=email,
            password_hash="$2b$12$demo.demo.demo.demo.demo.demo.demo.demo",
            role="staff",
            dept_id=dept.id,
            status="active",
        )
        db.add(u)
        db.flush()
        out.append(u)
    return out


def _seed_docs(db: Session, depts: list[Department], users: list[User]) -> list[Document]:
    out = []
    for i, spec in enumerate(DEMO_DOCS):
        dept = depts[i % len(depts)]
        owner = users[i % len(users)]
        doc = Document(
            doc_name=spec["doc_name"],
            origin_file_name=f"{spec['doc_name']}.{spec['file_type']}",
            file_type=spec["file_type"],
            file_size=spec["file_size"],
            file_hash=f"{DEMO_HASH_PREFIX}{uuid.uuid4().hex[:12]}",
            dept_id=dept.id,
            upload_user_id=owner.id,
            status="success",
            progress=100,
            summary=f"演示文档：{spec['chunks'][0]}",
            view_count=18 + i * 9,
            retrieve_count=12 + i * 7,
            kg_status="success",
            kg_entity_count=4,
            kg_relation_count=3,
        )
        db.add(doc)
        db.flush()
        for idx, text in enumerate(spec["chunks"]):
            db.add(
                DocChunk(
                    doc_id=doc.id,
                    chunk_text=text,
                    page_no=(idx % 2) + 1,
                    chunk_index=idx,
                    chroma_id=str(uuid.uuid4()),
                )
            )
        out.append(doc)
    return out


def _seed_kg(db: Session, docs: list[Document]) -> dict:
    entities = []
    relations = []
    # P1-7：原实现每个文档各查一次实体 / 关系（2N 次查询），改为按全部 doc_id 一次 IN 预加载
    doc_ids = [d.id for d in docs]
    ent_by_doc: dict[int, dict[str, int]] = {}
    rel_by_doc: dict[int, set] = {}
    if doc_ids:
        for e in db.query(Entity).filter(Entity.doc_id.in_(doc_ids)).all():
            ent_by_doc.setdefault(e.doc_id, {})[e.entity_name] = e.id
        for r in (
            db.query(EntityRelation)
            .filter(EntityRelation.doc_id.in_(doc_ids))
            .with_entities(
                EntityRelation.doc_id,
                EntityRelation.source_entity_id,
                EntityRelation.target_entity_id,
                EntityRelation.relation_type,
            )
            .all()
        ):
            rel_by_doc.setdefault(r.doc_id, set()).add((r.source_entity_id, r.target_entity_id, r.relation_type))
    for doc in docs:
        existing_ent = ent_by_doc.setdefault(doc.id, {})
        for name, etype in DEMO_ENTITIES:
            if name in existing_ent:
                entities.append((name, existing_ent[name]))
                continue
            ent = Entity(
                entity_name=name,
                entity_type=etype,
                description=f"演示实体：{name}（来源《{doc.doc_name}》）",
                doc_id=doc.id,
                chunk_id=str(uuid.uuid4()),
                source="demo",
            )
            db.add(ent)
            db.flush()
            existing_ent[name] = ent.id
            entities.append((name, ent.id))
        name_map = {n: eid for n, eid in entities}
        existing_rel = rel_by_doc.setdefault(doc.id, set())
        for src, tgt, rel in DEMO_RELATIONS:
            if src not in name_map or tgt not in name_map:
                continue
            key = (name_map[src], name_map[tgt], rel)
            if key in existing_rel:
                continue
            db.add(
                EntityRelation(
                    source_entity_id=name_map[src],
                    target_entity_id=name_map[tgt],
                    relation_type=rel,
                    doc_id=doc.id,
                    chunk_id=str(uuid.uuid4()),
                    source="demo",
                )
            )
            existing_rel.add(key)
            relations.append((src, tgt, rel))
    return {"entities": len(entities), "relations": len(relations)}


def _seed_conversations(db: Session, users: list[User], docs: list[Document]) -> int:
    qa_pairs = [
        ("智研 X1 的上市节奏是怎样的？", "智研 X1 智能办公终端上市分三个阶段：预热期发布白皮书并邀请头部客户内测，引爆期联合渠道伙伴举办城市发布会，收割期推出企业采购优惠方案并扩大直销团队。"),
        ("研发效能改进的三板斧是什么？", "研发效能改进三板斧：度量先行、自动化提效、知识沉淀。通过统一效能平台采集需求交付周期、缺陷密度、发布频率指标，配合 CI/CD 与知识问答体系持续改进。"),
        ("知寻 KnowSeek 在金融行业的落地效果如何？", "某头部证券公司基于知寻 KnowSeek 构建投研知识中台，沉淀研报与合规文档 12 万份，检索准确率提升至 92%，研究员日均节省 1.5 小时。"),
    ]
    count = 0
    for i, (q, a) in enumerate(qa_pairs):
        user = users[i % len(users)]
        conv = Conversation(user_id=user.id, title=q[:24])
        db.add(conv)
        db.flush()
        db.add(ConversationMsg(conv_id=conv.id, role="user", content=q))
        db.add(ConversationMsg(conv_id=conv.id, role="assistant", content=a))
        count += 1
    return count


def _seed_activity(db: Session, depts: list[Department], users: list[User]) -> int:
    """演示活跃数据：近 14 日检索日志（module=chat, detail 标记演示）+ 近 14 日 LLM 调用日志。"""
    today = date.today()
    now = datetime.now()
    for day_offset in range(14):
        d = today - timedelta(days=day_offset)
        base = datetime.combine(d, datetime.min.time()).replace(hour=9)
        for dept, user in zip(depts * 4, users * 4):
            for _k in range(2 + (day_offset % 3)):
                db.add(
                    OperationLog(
                        user_id=user.id,
                        username=user.username,
                        dept_id=dept.id,
                        action="GET",
                        module="chat",
                        method="GET",
                        path="/api/chat/ask",
                        detail=DEMO_OP_MARK,
                        status="success",
                        duration_ms=600 + day_offset * 20,
                        create_time=base + timedelta(hours=day_offset % 8, minutes=_k * 7),
                    )
                )
    for day_offset in range(14):
        d = today - timedelta(days=day_offset)
        base = datetime.combine(d, datetime.min.time()).replace(hour=10)
        for i in range(2 + (day_offset % 2)):
            ok_flag = day_offset % 5 != 4
            db.add(
                LlmCallLog(
                    user_id=users[i % len(users)].id,
                    scenario="demo",
                    model_name="DeepSeek-V3",
                    prompt_tokens=1200 + day_offset * 30,
                    completion_tokens=600 + day_offset * 12,
                    total_tokens=1800 + day_offset * 42,
                    latency_ms=2400 - day_offset * 40,
                    is_success=ok_flag,
                    error_msg="" if ok_flag else "上游超时（演示数据）",
                    create_time=base + timedelta(hours=i * 2),
                )
            )
    return 14 * 2


def seed_demo(db: Session, keep_original: bool = True) -> dict:
    # ===== 逐行注释：一键灌入演示数据（核心）=====
    # 1. keep_original=False 时先 clear_demo 清空旧演示数据（幂等重灌）；
    # 2. _demo_departments：创建或复用 "[演示]" 前缀部门（市场部/研发部）；
    # 3. _demo_users：创建或复用 demo_ 前缀邮箱用户（密码哈希为占位值，仅演示登录）；
    # 4. _seed_docs：按 DEMO_DOCS 规格写入演示文档 + 切片（file_hash 带 demo- 前缀标记）；
    # 5. _seed_kg：写入演示实体/关系（source="demo" 标记），驱动知识图谱页展示；
    # 6. _seed_conversations：写入演示问答对（对话/消息），驱动聊天页展示；
    # 7. _seed_activity：回填近 14 日检索日志（detail="[demo-seed]"）与 LLM 调用日志
    #    （scenario="demo"），让看板热力图/趋势/用量报表有真实可聚合的演示数据；
    # 8. 最后写 SysConfig.demo_active=1 作为演示模式开关，返回统计供前端提示。
    if not keep_original:
        clear_demo(db)
    depts = _demo_departments(db)
    users = _demo_users(db, depts)
    docs = _seed_docs(db, depts, users)
    kg = _seed_kg(db, docs)
    conv_count = _seed_conversations(db, users, docs)
    _seed_activity(db, depts, users)
    db.commit()

    cfg = db.query(SysConfig).filter(SysConfig.config_key == "demo_active").first()
    if not cfg:
        cfg = SysConfig(config_key="demo_active", config_value="1", description="演示模式激活标记")
        db.add(cfg)
    cfg.config_value = "1"
    cfg.update_time = now = datetime.now()
    db.commit()

    return {
        "active": True,
        "seeded_at": now.isoformat(),
        "departments": len(depts),
        "users": len(users),
        "documents": len(docs),
        "entities": kg["entities"],
        "relations": kg["relations"],
        "conversations": conv_count,
        "keep_original": keep_original,
    }


def demo_status(db: Session) -> dict:
    cfg = db.query(SysConfig).filter(SysConfig.config_key == "demo_active").first()
    active = bool(cfg and cfg.config_value == "1")
    seeded_at = cfg.update_time.isoformat() if (cfg and cfg.update_time) else None
    counts = {
        "departments": db.query(func.count(Department.id)).filter(Department.dept_name.like(f"{DEMO_DEPT_PREFIX}%")).scalar() or 0,
        "users": db.query(func.count(User.id)).filter(User.email.like(f"{DEMO_EMAIL_PREFIX}%")).scalar() or 0,
        # P1-6 软删过滤：演示文档进回收站后不再计入统计，避免演示数据量虚高
        "documents": db.query(func.count(Document.id)).filter(
            Document.file_hash.like(f"{DEMO_HASH_PREFIX}%"), Document.is_deleted.is_(False)
        ).scalar() or 0,
        "llm_logs": db.query(func.count(LlmCallLog.id)).filter(LlmCallLog.scenario == "demo").scalar() or 0,
    }
    return {"active": active, "seeded_at": seeded_at, "counts": counts}


def clear_demo(db: Session) -> dict:
    doc_ids = [r[0] for r in db.query(Document.id).filter(Document.file_hash.like(f"{DEMO_HASH_PREFIX}%")).all()]
    user_ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{DEMO_EMAIL_PREFIX}%")).all()]

    if doc_ids:
        db.query(DocChunk).filter(DocChunk.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(Entity).filter(Entity.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(EntityRelation).filter(EntityRelation.doc_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(synchronize_session=False)
    if user_ids:
        conv_ids = [r[0] for r in db.query(Conversation.id).filter(Conversation.user_id.in_(user_ids)).all()]
        if conv_ids:
            db.query(ConversationMsg).filter(ConversationMsg.conv_id.in_(conv_ids)).delete(synchronize_session=False)
            db.query(Conversation).filter(Conversation.id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.query(Department).filter(Department.dept_name.like(f"{DEMO_DEPT_PREFIX}%")).delete(synchronize_session=False)
    db.query(LlmCallLog).filter(LlmCallLog.scenario == "demo").delete(synchronize_session=False)
    db.query(OperationLog).filter(OperationLog.detail == DEMO_OP_MARK).delete(synchronize_session=False)
    db.query(SysConfig).filter(SysConfig.config_key == "demo_active").delete(synchronize_session=False)
    db.commit()
    return {"cleared": True, "removed_documents": len(doc_ids), "removed_users": len(user_ids)}
