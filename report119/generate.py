#!/usr/bin/env python3
"""119 관제내역 → 상황보고서 HWPX 자동 생성기.

JSON 데이터를 읽어 119 상황보고서 HWPX 문서를 자동 생성합니다.

사용법:
    # 전체 건 하나의 보고서로 생성
    python generate.py -i sample_data.json -o output/

    # 특정 사건번호만 생성
    python generate.py -i data.json -o output/ --case "2026-031523-001"
"""

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
BUILD_SCRIPT = SKILL_DIR / "scripts" / "build_hwpx.py"

# HWPX XML 네임스페이스
NS = textwrap.dedent("""\
    xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" \
    xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" \
    xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app" \
    xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph" \
    xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core" \
    xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" \
    xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history" \
    xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page" \
    xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" \
    xmlns:dc="http://purl.org/dc/elements/1.1/" \
    xmlns:opf="http://www.idpf.org/2007/opf/" \
    xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart" \
    xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar" \
    xmlns:epub="http://www.idpf.org/2007/ops" \
    xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"\
""").replace("\n", " ")

BODY_WIDTH = 42520


class IDGen:
    """고유 ID 생성기."""
    def __init__(self, start=1000000001):
        self._n = start

    def next(self):
        v = self._n
        self._n += 1
        return v


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def empty_p(ids: IDGen) -> str:
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def text_p(ids: IDGen, text: str, charPr: int = 0, paraPr: int = 0) -> str:
    vs = 1800 if charPr == 7 else (1200 if charPr == 8 else 1000)
    bl = int(vs * 0.85)
    sp = int(vs * 0.6)
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="{paraPr}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="{charPr}">
      <hp:t>{_esc(text)}</hp:t>
    </hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="{vs}" textheight="{vs}" baseline="{bl}" spacing="{sp}" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def table_row_2col(ids: IDGen, label: str, value: str, row_addr: int,
                   label_w: int = 8504, row_h: int = 2400,
                   label_charPr: int = 9, value_charPr: int = 0) -> str:
    """2열 테이블 행 (라벨 | 값)."""
    value_w = BODY_WIDTH - label_w
    ltw = label_w - 566
    vtw = value_w - 566
    return f"""\
        <hp:tr>
          <hp:tc borderFillIDRef="4">
            <hp:cellAddr colAddr="0" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{label_w}" height="{row_h}"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="{ltw}" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="{label_charPr}">
                  <hp:t>{_esc(label)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="{ltw}" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>
          <hp:tc borderFillIDRef="3">
            <hp:cellAddr colAddr="1" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{value_w}" height="{row_h}"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="{vtw}" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="{value_charPr}">
                  <hp:t>{_esc(value)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="{vtw}" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>
        </hp:tr>"""


def full_width_row(ids: IDGen, text: str, row_addr: int, row_h: int = 4800,
                   charPr: int = 0) -> str:
    """전체 너비 1열 행 (긴 텍스트용)."""
    tw = BODY_WIDTH - 566
    return f"""\
        <hp:tr>
          <hp:tc borderFillIDRef="3">
            <hp:cellAddr colAddr="0" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="2" rowSpan="1"/>
            <hp:cellSz width="{BODY_WIDTH}" height="{row_h}"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" textWidth="{tw}" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="{charPr}">
                  <hp:t>{_esc(text)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="{tw}" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>
        </hp:tr>"""


def make_table(ids: IDGen, rows_xml: str, row_count: int, total_h: int) -> str:
    """테이블을 감싸는 문단 XML."""
    tbl_id = ids.next()
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
        <hp:sz width="{BODY_WIDTH}" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="0" right="0" top="0" bottom="0"/>
        <hp:inMargin left="0" right="0" top="0" bottom="0"/>
{rows_xml}
      </hp:tbl>
    </hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def secpr_p(ids: IDGen) -> str:
    """첫 문단 (페이지 설정)."""
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="1" memoShapeIDRef="0" textVerticalWidthHead="0" masterPageCnt="0">
        <hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0"/>
        <hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>
        <hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>
        <hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>
        <hp:pagePr landscape="WIDELY" width="59528" height="84186" gutterType="LEFT_ONLY">
          <hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>
        </hp:pagePr>
        <hp:footNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="-1" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="283" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="EACH_COLUMN" beneathText="0"/>
        </hp:footNotePr>
        <hp:endNotePr>
          <hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>
          <hp:noteLine length="14692344" type="SOLID" width="0.12 mm" color="#000000"/>
          <hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>
          <hp:numbering type="CONTINUOUS" newNum="1"/>
          <hp:placement place="END_OF_DOCUMENT" beneathText="0"/>
        </hp:endNotePr>
        <hp:pageBorderFill type="BOTH" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="EVEN" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
        <hp:pageBorderFill type="ODD" borderFillIDRef="1" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">
          <hp:offset left="1417" right="1417" top="1417" bottom="1417"/>
        </hp:pageBorderFill>
      </hp:secPr>
      <hp:ctrl>
        <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>
      </hp:ctrl>
    </hp:run>
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def page_break_p(ids: IDGen) -> str:
    """페이지 나눔 문단."""
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="1" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def estimate_row_h(text: str, cell_width: int = 33450, line_h: int = 1200,
                   min_h: int = 2400) -> int:
    """텍스트 길이에 따른 셀 높이 추정 (줄바꿈, 긴 텍스트 대응)."""
    # 셀 너비 기준 한 줄에 들어가는 글자 수 (HWPUNIT → 대략 글자)
    chars_per_line = max(1, cell_width // 280)  # 10pt 기준 약 280 HWPUNIT/글자
    lines = 0
    for paragraph in text.split("\n"):
        lines += max(1, -(-len(paragraph) // chars_per_line))  # ceil division
    return max(min_h, lines * line_h + 400)  # 400 = 상하 여백


def generate_incident_block(ids: IDGen, inc: dict, index: int,
                            is_first: bool = True) -> list[str]:
    """사건 1건의 상황보고서 블록 생성."""
    parts = []

    # 2건째부터 페이지 나눔
    if not is_first:
        parts.append(page_break_p(ids))

    # 사건 번호 제목
    parts.append(text_p(ids, f"[{index}] 사건번호: {inc['case_number']}", charPr=8))

    # 기본 정보 테이블
    basic_rows = [
        ("접수일시", inc["received_at"]),
        ("사고유형", f"{inc['type']} / {inc['sub_type']}"),
        ("신고자", f"{inc['caller']}  ({inc.get('caller_phone', '')})"),
        ("발생장소", inc["location"]),
        ("출동대", " / ".join(inc["dispatched_units"])),
        ("출동시각", inc.get("dispatch_time", "")),
        ("도착시각", inc.get("arrival_time", "")),
    ]
    row_h = 2400
    rows_xml = "\n".join(
        table_row_2col(ids, label, value, i, row_h=row_h)
        for i, (label, value) in enumerate(basic_rows)
    )
    total_h = row_h * len(basic_rows)
    parts.append(make_table(ids, rows_xml, len(basic_rows), total_h))

    parts.append(empty_p(ids))

    # 상황 내용
    parts.append(text_p(ids, "상황 내용", charPr=8))

    value_w = BODY_WIDTH - 8504 - 566  # 값 셀의 텍스트 너비
    sit_h = estimate_row_h(inc["situation"], value_w)
    situation_rows = table_row_2col(
        ids, "상황개요", inc["situation"], 0, row_h=sit_h
    )
    # 조치사항
    actions_text = "\n".join(f"  {a}" for a in inc["actions"])
    act_h = estimate_row_h(actions_text, value_w, min_h=3600)
    situation_rows += "\n" + table_row_2col(
        ids, "조치사항", actions_text, 1, row_h=act_h
    )
    # 인명피해
    cas_h = estimate_row_h(inc.get("casualties", "없음"), value_w)
    situation_rows += "\n" + table_row_2col(
        ids, "인명피해", inc.get("casualties", "없음"), 2, row_h=cas_h
    )
    # 재산피해
    dmg_h = estimate_row_h(inc.get("damage", "없음"), value_w)
    situation_rows += "\n" + table_row_2col(
        ids, "재산피해", inc.get("damage", "없음"), 3, row_h=dmg_h
    )
    # 처리결과
    res_h = estimate_row_h(inc.get("result", ""), value_w)
    situation_rows += "\n" + table_row_2col(
        ids, "처리결과", inc.get("result", ""), 4, row_h=res_h
    )

    detail_h = sit_h + act_h + cas_h + dmg_h + res_h
    parts.append(make_table(ids, situation_rows, 5, detail_h))

    parts.append(empty_p(ids))

    return parts


def generate_section_xml(data: dict) -> str:
    """상황보고서 전체 section0.xml 생성."""
    ids = IDGen()
    parts = []

    # 페이지 설정
    parts.append(secpr_p(ids))
    parts.append(empty_p(ids))

    # 제목
    parts.append(text_p(ids, "119 상황보고서", charPr=7, paraPr=20))
    parts.append(empty_p(ids))

    # 기관 정보
    parts.append(text_p(ids, data["agency"], charPr=0, paraPr=20))
    parts.append(empty_p(ids))

    # 보고 기본 정보
    header_rows = [
        ("보고일자", data["report_date"]),
        ("보고부서", data.get("department", "")),
        ("작 성 자", data.get("reporter", "")),
        ("총 건 수", f"{len(data['incidents'])}건"),
    ]
    row_h = 2400
    header_xml = "\n".join(
        table_row_2col(ids, l, v, i, row_h=row_h)
        for i, (l, v) in enumerate(header_rows)
    )
    parts.append(make_table(ids, header_xml, len(header_rows), row_h * len(header_rows)))
    parts.append(empty_p(ids))
    parts.append(empty_p(ids))

    # 사건별 상세
    parts.append(text_p(ids, "상황 상세 내역", charPr=7, paraPr=20))
    parts.append(empty_p(ids))

    for i, inc in enumerate(data["incidents"], 1):
        parts.extend(generate_incident_block(ids, inc, i, is_first=(i == 1)))

    # 서명란
    parts.append(empty_p(ids))
    parts.append(text_p(ids, f"작성: {data.get('reporter', '')}",  paraPr=20))
    parts.append(text_p(ids, f"{data['agency']} {data.get('department', '')}", paraPr=20))

    xml = f"<?xml version='1.0' encoding='UTF-8'?>\n<hs:sec {NS}>\n"
    xml += "\n".join(parts)
    xml += "\n</hs:sec>"
    return xml


def main():
    parser = argparse.ArgumentParser(description="119 관제내역 → 상황보고서 자동 생성")
    parser.add_argument("-i", "--input", type=Path, required=True, help="관제내역 JSON 파일")
    parser.add_argument("-o", "--output", type=Path, default=Path("output"), help="출력 디렉토리")
    parser.add_argument("--case", help="특정 사건번호만 생성")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    args.output.mkdir(parents=True, exist_ok=True)

    if args.case:
        data["incidents"] = [
            inc for inc in data["incidents"] if inc["case_number"] == args.case
        ]
        if not data["incidents"]:
            print(f"사건번호 '{args.case}'을(를) 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)

    section_xml = generate_section_xml(data)

    section_path = args.output / "_tmp_119report_section.xml"
    section_path.write_text(section_xml, encoding="utf-8")

    filename = f"상황보고서_{data['report_date']}_{data['agency']}.hwpx"
    output_path = args.output / filename
    title = f"119 상황보고서 - {data['report_date']}"

    result = subprocess.run(
        [
            sys.executable, str(BUILD_SCRIPT),
            "--template", "report",
            "--section", str(section_path),
            "--title", title,
            "--creator", data.get("reporter", ""),
            "--output", str(output_path),
        ],
        capture_output=True, text=True,
    )

    section_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"[실패] {result.stderr}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"[완료] {output_path}")
        print(f"총 {len(data['incidents'])}건 상황보고서 생성 완료")


if __name__ == "__main__":
    main()
