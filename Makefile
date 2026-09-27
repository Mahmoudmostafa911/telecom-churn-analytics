# Convenience targets (Windows users: run the same commands from PowerShell, or `make` via Git Bash)
PY ?= python
export PYTHONPATH := src

.PHONY: all data fixture kpis run test clean

all: data kpis run            ## download real data, generate telemetry, run everything

data:                         ## download the IBM Telco file
	$(PY) data/download_data.py

fixture:                      ## build the synthetic stand-in + telemetry (no internet needed)
	$(PY) data/make_synthetic_fixture.py
	$(PY) data/generate_network_kpis.py --customers data/raw/telco_synthetic_fixture.csv

kpis:                         ## generate telemetry for the real customer list
	$(PY) data/generate_network_kpis.py

run:                          ## full pipeline on the real file
	$(PY) -m telco_churn run

run-fixture:                  ## full pipeline on the synthetic fixture
	$(PY) -m telco_churn run --fixture

test:                         ## unit tests
	$(PY) -m pytest tests -q || $(PY) -m unittest discover -s tests

clean:
	rm -rf data/processed/* docs/findings.md model/metrics.json model/drivers_*.csv model/lift_*.csv
