from pathlib import Path

import pytest

from lastmile.config import REPO_ROOT, load_settings
from lastmile.data import load_abc_instance, load_case_instance

RAW = REPO_ROOT / "data" / "raw"


@pytest.fixture(scope="session")
def nagpur():
    return load_case_instance(RAW / "02_Main_Case_Data_File.xlsx")


@pytest.fixture(scope="session")
def abc():
    return load_abc_instance(RAW / "abc_warehouse.csv")


@pytest.fixture(scope="session")
def model_file() -> Path:
    return RAW / "01_IIM_Indore_project_for_SCM_MDP.xlsm"


@pytest.fixture(scope="session")
def case_file() -> Path:
    return RAW / "02_Main_Case_Data_File.xlsx"


@pytest.fixture(scope="session")
def settings():
    return load_settings("smoke")
