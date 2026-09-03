from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "replyflow_case_study.pdf"


def main() -> None:
    pdfmetrics.registerFont(TTFont("MSYH", r"C:\Windows\Fonts\simhei.ttf"))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CNTitle", parent=styles["Title"], fontName="MSYH", fontSize=20, leading=26, textColor=colors.HexColor("#172554"), alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="CNH2", parent=styles["Heading2"], fontName="MSYH", fontSize=13, leading=18, textColor=colors.HexColor("#172554"), spaceBefore=10, spaceAfter=5))
    styles.add(ParagraphStyle(name="CNBody", parent=styles["BodyText"], fontName="MSYH", fontSize=8.7, leading=13, textColor=colors.HexColor("#334155"), spaceAfter=4))
    styles.add(ParagraphStyle(name="CNSmall", parent=styles["BodyText"], fontName="MSYH", fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b")))
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    story = [
        Paragraph("ReplyFlow｜高风险售后 Agent 评测与人机协同工作台", styles["CNTitle"]),
        Paragraph("一个搭载在电商邮件系统顶部聚合站内信上的 AI 回复能力原型：低风险更快处理，中风险人工确认，高风险发送前拦截。", styles["CNBody"]),
        Paragraph("演示边界：邮件、订单、物流、发送和 ROI 均为虚构或本地模拟；不连接真实 Amazon、邮箱、支付或订单写入接口。Coze 只负责 Analyze/Draft，本地控制层负责事实、风险、状态、确认、幂等和审计。", styles["CNBody"]),
        Paragraph("01｜产品定位", styles["CNH2"]),
        Paragraph("ReplyFlow 保留原客服邮件工作台，在顶部聚合站内信上增量接入单 Agent。右下角模拟邮件台可输入一行邮件、选择虚构订单并真实改变本地 SQLite 状态。", styles["CNBody"]),
        Paragraph("02｜处理链路", styles["CNH2"]),
        Paragraph("模拟接入 → 原始收件箱 → 顶部聚合站内信 → Coze Analyze/Draft → 本地事实与风险网关 → L1 自动发送 / L2 草稿确认 / L3 高风险核对 → 本地模拟 outbox。", styles["CNBody"]),
        Paragraph("03｜架构取舍", styles["CNH2"]),
        Paragraph("Coze 用于快速编排模型分析和草稿生成；自建控制层负责 8 个 MCP Tools、3 个 Skills、订单/物流事实、只读回复依据、R0–R3 风险、L1–L3 状态机、确认、幂等和审计。", styles["CNBody"]),
        Paragraph("04｜评测证据", styles["CNH2"]),
    ]
    data = [
        [Paragraph("指标", styles["CNSmall"]), Paragraph("结果", styles["CNSmall"]), Paragraph("解释", styles["CNSmall"])],
        [Paragraph("离线案例", styles["CNSmall"]), Paragraph("30（R2：13）", styles["CNSmall"]), Paragraph("Demo 评测集，含高风险切片", styles["CNSmall"])],
        [Paragraph("动态接入率", styles["CNSmall"]), Paragraph("100%（29/29）", styles["CNSmall"]), Paragraph("模拟邮件能进入聚合流程", styles["CNSmall"])],
        [Paragraph("Demo / Interactive 未授权承诺", styles["CNSmall"]), Paragraph("0 / 1", styles["CNSmall"]), Paragraph("Demo 通过；Interactive 复测发现 1 条", styles["CNSmall"])],
        [Paragraph("无依据订单事实违规", styles["CNSmall"]), Paragraph("0", styles["CNSmall"]), Paragraph("事实来自本地 Tool/依据层", styles["CNSmall"])],
        [Paragraph("Demo / Interactive 高风险召回", styles["CNSmall"]), Paragraph("61.5%（8/13）", styles["CNSmall"]), Paragraph("两种模式均未达安全门槛，自动决策 No-Go", styles["CNSmall"])],
        [Paragraph("Interactive 结构校验", styles["CNSmall"]), Paragraph("26/30", styles["CNSmall"]), Paragraph("4 条 Coze 输出未通过本地 Schema 校验", styles["CNSmall"])],
    ]
    tbl = Table(data, colWidths=[40 * mm, 36 * mm, 100 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "MSYH"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#dbe4f0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(tbl)
    story.extend([
        Paragraph("05｜边界与限制", styles["CNH2"]),
        Paragraph("2026-09-03 Interactive 复测时 Coze 额度可用，30 条案例完成评测；高风险召回 61.5%（8/13）、意图准确率 64.3%（18/28），出现 1 条未授权承诺和 4 条结构校验失败，因此仍为 No-Go。项目不连接真实 Amazon、邮箱、支付或订单接口，不包含主管/审批、多 Agent、政策治理等扩展范围。ROI 仅为虚构敏感性分析，不代表真实收益。", styles["CNBody"]),
        Spacer(1, 4 * mm),
        Paragraph("运行：.venv\\Scripts\\python.exe stage_b_server.py --port 8511 · http://127.0.0.1:8511/", styles["CNSmall"]),
    ])
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    main()
