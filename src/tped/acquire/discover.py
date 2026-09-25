"""端點契約（spec §3.1）——站方改版時只需改此檔。"""

from urllib.parse import urljoin

from ..config import BASE_URL, T_PARAM


def year_list_url(year_ce: int) -> str:
    return f"{BASE_URL}wFrmExamQandASearch.aspx?y={year_ce}"


def subject_list_url(exam_code: str) -> str:
    return f"{BASE_URL}wFrmExamQandASearch.aspx?y={int(exam_code[:3]) + 1911}&e={exam_code}"


def file_url(relative_href: str) -> str:
    return urljoin(BASE_URL, relative_href)


def expected_file_href(kind: str, exam_code: str, category_code: str, subject_file_code: str) -> str:
    return f"wHandExamQandA_File.ashx?t={T_PARAM[kind]}&code={exam_code}&c={category_code}&s={subject_file_code}&q=1"
