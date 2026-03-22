#!/usr/bin/env python3
"""유치원 관찰일지 자동 생성기.

JSON 데이터를 읽어 아동별 관찰일지 HWPX 문서를 자동 생성합니다.

사용법:
    # 샘플 데이터로 생성
    python generate.py -i sample_data.json -o output/

    # 특정 아동만 생성
    python generate.py -i data.json -o output/ --child "이서준"
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

# 본문 너비 (A4 - 좌우마진)
BODY_WIDTH = 42520


class IDGen:
    """고유 ID 생성기."""
    def __init__(self, start=1000000001):
        self._n = start

    def next(self):
        v = self._n
        self._n += 1
        return v


def empty_p(ids: IDGen) -> str:
    """빈 줄 XML."""
    return f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>"""


def text_p(ids: IDGen, text: str, charPr: int = 0, paraPr: int = 0) -> str:
    """텍스트 문단 XML."""
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


def _esc(text: str) -> str:
    """XML 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def meta_row(ids: IDGen, label: str, value: str, row_addr: int) -> str:
    """메타 정보 테이블 행."""
    label_w = 8504
    value_w = BODY_WIDTH - label_w
    return f"""\
        <hp:tr>
          <hp:tc borderFillIDRef="4">
            <hp:cellAddr colAddr="0" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{label_w}" height="2400"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="7938" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="9">
                  <hp:t>{_esc(label)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="7938" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>
          <hp:tc borderFillIDRef="3">
            <hp:cellAddr colAddr="1" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{value_w}" height="2400"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="33450" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="0">
                  <hp:t>{_esc(value)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="33450" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>
        </hp:tr>"""


def obs_table_header(ids: IDGen, row_addr: int) -> str:
    """관찰기록 테이블 헤더 행 (날짜 | 영역 | 관찰 내용)."""
    cols = [
        ("날짜", 5670),
        ("영역", 7088),
        ("관찰 내용", 29762),
    ]
    cells = []
    for col_i, (label, w) in enumerate(cols):
        tw = w - 566  # cellMargin left+right
        cells.append(f"""\
          <hp:tc borderFillIDRef="4">
            <hp:cellAddr colAddr="{col_i}" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{w}" height="2000"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="{tw}" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="9">
                  <hp:t>{_esc(label)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="{tw}" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>""")
    return f"        <hp:tr>\n" + "\n".join(cells) + "\n        </hp:tr>"


def obs_table_row(ids: IDGen, obs: dict, row_addr: int) -> str:
    """관찰기록 데이터 행."""
    cols = [
        (obs["date"], 5670),
        (obs["area"], 7088),
        (obs["observation"], 29762),
    ]
    cells = []
    for col_i, (text, w) in enumerate(cols):
        tw = w - 566
        cells.append(f"""\
          <hp:tc borderFillIDRef="3">
            <hp:cellAddr colAddr="{col_i}" rowAddr="{row_addr}"/>
            <hp:cellSpan colSpan="1" rowSpan="1"/>
            <hp:cellSz width="{w}" height="3600"/>
            <hp:cellMargin left="283" right="283" top="141" bottom="141"/>
            <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="{tw}" fieldName="">
              <hp:p id="{ids.next()}" paraPrIDRef="22" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
                <hp:run charPrIDRef="0">
                  <hp:t>{_esc(text)}</hp:t>
                </hp:run>
                <hp:linesegarray>
                  <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="300" horzpos="0" horzsize="{tw}" flags="393216"/>
                </hp:linesegarray>
              </hp:p>
            </hp:subList>
          </hp:tc>""")
    return f"        <hp:tr>\n" + "\n".join(cells) + "\n        </hp:tr>"


def eval_section(ids: IDGen, observations: list[dict]) -> str:
    """총평 섹션 XML."""
    lines = []
    lines.append(text_p(ids, "종합 평가", charPr=8))
    lines.append(empty_p(ids))
    for obs in observations:
        lines.append(text_p(ids, f"  ■ {obs['area']}"))
        lines.append(text_p(ids, f"    {obs['evaluation']}"))
        lines.append(empty_p(ids))
    return "\n".join(lines)


def generate_section_xml(data: dict, child: dict) -> str:
    """아동 1명의 관찰일지 section0.xml 생성."""
    ids = IDGen()
    parts = []

    # secPr (첫 문단 - 페이지 설정)
    parts.append(f"""\
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
  </hp:p>""")

    # 빈줄
    parts.append(empty_p(ids))

    # 제목
    title = f"{data['year']}년 {data['month']}월 유아 관찰일지"
    parts.append(text_p(ids, title, charPr=7, paraPr=20))
    parts.append(empty_p(ids))

    # 기관명
    parts.append(text_p(ids, data["kindergarten"], charPr=0, paraPr=20))
    parts.append(empty_p(ids))

    # 메타 정보 테이블
    meta_rows_data = [
        ("반    명", data["class_name"]),
        ("유아 이름", child["name"]),
        ("나    이", f"만 {child['age']}세"),
        ("담당 교사", data["teacher"]),
        ("관찰 기간", f"{data['year']}년 {data['month']}월"),
    ]
    total_h = 2400 * len(meta_rows_data)
    tbl_id = ids.next()
    meta_rows_xml = "\n".join(
        meta_row(ids, label, value, i)
        for i, (label, value) in enumerate(meta_rows_data)
    )

    parts.append(f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
        <hp:sz width="{BODY_WIDTH}" widthRelTo="ABSOLUTE" height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="0" right="0" top="0" bottom="0"/>
        <hp:inMargin left="0" right="0" top="0" bottom="0"/>
{meta_rows_xml}
      </hp:tbl>
    </hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>""")

    parts.append(empty_p(ids))
    parts.append(empty_p(ids))

    # 관찰 기록 테이블
    observations = child["observations"]
    obs_row_cnt = 1 + len(observations)  # header + data rows
    obs_total_h = 2000 + 3600 * len(observations)
    obs_tbl_id = ids.next()

    header_row = obs_table_header(ids, 0)
    data_rows = "\n".join(
        obs_table_row(ids, obs, i + 1)
        for i, obs in enumerate(observations)
    )

    parts.append(text_p(ids, "관찰 기록", charPr=8))
    parts.append(f"""\
  <hp:p id="{ids.next()}" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:tbl id="{obs_tbl_id}" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="0" cellSpacing="0" borderFillIDRef="3" noAdjust="0">
        <hp:sz width="{BODY_WIDTH}" widthRelTo="ABSOLUTE" height="{obs_total_h}" heightRelTo="ABSOLUTE" protect="0"/>
        <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
        <hp:outMargin left="0" right="0" top="0" bottom="0"/>
        <hp:inMargin left="0" right="0" top="0" bottom="0"/>
{header_row}
{data_rows}
      </hp:tbl>
    </hp:run>
    <hp:linesegarray>
      <hp:lineseg textpos="0" vertpos="0" vertsize="1000" textheight="1000" baseline="850" spacing="600" horzpos="0" horzsize="{BODY_WIDTH}" flags="393216"/>
    </hp:linesegarray>
  </hp:p>""")

    parts.append(empty_p(ids))
    parts.append(empty_p(ids))

    # 종합 평가
    parts.append(eval_section(ids, observations))

    # 서명란
    parts.append(empty_p(ids))
    parts.append(text_p(ids, f"담당교사 :  {data['teacher']}  (서명)", paraPr=20))

    # 조합
    xml = f'<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n<hs:sec {NS}>\n'
    xml += "\n".join(parts)
    xml += "\n</hs:sec>"
    return xml


def main():
    parser = argparse.ArgumentParser(description="유치원 관찰일지 자동 생성")
    parser.add_argument("-i", "--input", type=Path, required=True, help="관찰 데이터 JSON 파일")
    parser.add_argument("-o", "--output", type=Path, default=Path("output"), help="출력 디렉토리")
    parser.add_argument("--child", help="특정 아동 이름만 생성")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    args.output.mkdir(parents=True, exist_ok=True)

    children = data["children"]
    if args.child:
        children = [c for c in children if c["name"] == args.child]
        if not children:
            print(f"아동 '{args.child}'을(를) 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)

    for child in children:
        section_xml = generate_section_xml(data, child)

        # 임시 section XML 저장
        section_path = args.output / f"_tmp_{child['name']}_section.xml"
        section_path.write_text(section_xml, encoding="utf-8")

        filename = f"관찰일지_{data['year']}년{data['month']:02d}월_{child['name']}.hwpx"
        output_path = args.output / filename
        title = f"{data['year']}년 {data['month']}월 관찰일지 - {child['name']}"

        result = subprocess.run(
            [
                sys.executable, str(BUILD_SCRIPT),
                "--template", "minutes",
                "--section", str(section_path),
                "--title", title,
                "--creator", data["teacher"],
                "--output", str(output_path),
            ],
            capture_output=True, text=True,
        )

        # 임시파일 삭제
        section_path.unlink(missing_ok=True)

        if result.returncode != 0:
            print(f"[실패] {child['name']}: {result.stderr}", file=sys.stderr)
        else:
            print(f"[완료] {output_path}")

    print(f"\n총 {len(children)}명 관찰일지 생성 완료")


if __name__ == "__main__":
    main()
