from pydantic import BaseModel
from typing import Optional


class ReportCreate(BaseModel):
    school_id: int
    report_year: int
    report_month: int
    academic_year: str
    students_school: Optional[int] = None
    students_community: Optional[int] = None
    students_girls: Optional[int] = None
    workshops_school: Optional[int] = None
    workshops_community: Optional[int] = None
    mentoring_school: Optional[int] = None
    mentoring_community: Optional[int] = None
    innovation_school: Optional[int] = None
    innovation_community: Optional[int] = None
    patents_school: Optional[int] = None
    patents_community: Optional[int] = None
    copyrights_school: Optional[int] = None
    copyrights_community: Optional[int] = None
    atl_competitions_participated: Optional[int] = None
    atl_competitions_won: Optional[int] = None
    other_competitions_participated: Optional[int] = None
    other_competitions_won: Optional[int] = None
    industrial_visits: Optional[int] = None
    ip_granted: Optional[int] = None
    ip_filed: Optional[int] = None
    highlight_of_month: Optional[str] = None
    social_post_link_1: Optional[str] = None
    social_post_link_2: Optional[str] = None
    social_post_link_3: Optional[str] = None


class ReportUpdate(BaseModel):
    students_school: Optional[int] = None
    students_community: Optional[int] = None
    students_girls: Optional[int] = None
    workshops_school: Optional[int] = None
    workshops_community: Optional[int] = None
    mentoring_school: Optional[int] = None
    mentoring_community: Optional[int] = None
    innovation_school: Optional[int] = None
    innovation_community: Optional[int] = None
    patents_school: Optional[int] = None
    patents_community: Optional[int] = None
    copyrights_school: Optional[int] = None
    copyrights_community: Optional[int] = None
    atl_competitions_participated: Optional[int] = None
    atl_competitions_won: Optional[int] = None
    other_competitions_participated: Optional[int] = None
    other_competitions_won: Optional[int] = None
    industrial_visits: Optional[int] = None
    ip_granted: Optional[int] = None
    ip_filed: Optional[int] = None
    highlight_of_month: Optional[str] = None
    social_post_link_1: Optional[str] = None
    social_post_link_2: Optional[str] = None
    social_post_link_3: Optional[str] = None
    review_notes: Optional[str] = None
