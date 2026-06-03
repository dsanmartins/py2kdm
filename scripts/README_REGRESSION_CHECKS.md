# py2kdm multilanguage KDM regression checks

This package adds an independent regression checker for generated KDM XMI files.

## Files

- `scripts/check_kdm_regression.py`
- `configs/kdm_regression_baselines.json`

## Usage

Python example:

```bash
python scripts/check_kdm_regression.py \
  --xmi outputs/pymape_hierarchical/model.kdm.xmi \
  --language python \
  --profile pymape_hierarchical \
  --baseline configs/kdm_regression_baselines.json
```

Java phoneadapter example:

```bash
python scripts/check_kdm_regression.py \
  --xmi outputs/phoneadapter/model.kdm.xmi \
  --language java \
  --profile phoneadapter \
  --baseline configs/kdm_regression_baselines.json
```

Java demo example:

```bash
python scripts/check_kdm_regression.py \
  --xmi outputs/demo-java-project/model.kdm.xmi \
  --language java \
  --profile demo_java_project \
  --baseline configs/kdm_regression_baselines.json
```

The checker exits with code 1 if a minimum threshold is not met or if a forbidden noisy external name appears.
