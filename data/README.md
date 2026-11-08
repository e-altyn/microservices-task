# Данные Lending Club

Источник: [Kaggle](https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv).

Для демонстрации используется `lending_club_sample.csv`

- Два класса: `Fully Paid` и `Charged Off` (0 и 1 соответственно). Другие исключены для простоты
- Период выдачи кредитов в выборке: июль 2007 — декабрь 2018 года
- Пропуски: `dti` — 2 строки, `revol_util` — 4 строки; остальные входные признаки заполнены
- 8 входных признаков, `loan_status` и `issue_d` для описания данных. Дата не входит в признаки модели

Имена, адреса, идентификаторы заемщиков и свободные тексты не переносятся. Из исходных колонок оставлены:

| Колонка | Назначение |
| --- | --- |
| loan_amnt | Сумма кредита |
| int_rate | Процентная ставка |
| annual_inc | Годовой доход |
| dti | Отношение долговых платежей к доходу |
| revol_util | Использование возобновляемого кредитного лимита |
| term | Срок кредита |
| home_ownership | Тип владения жильём |
| purpose | Цель кредита |
| loan_status | Известный исход кредита, только для обучения |
| issue_d | Месяц выдачи, справочное поле |

## Построение выборки с нуля

Команды выполняются из корня проекта. Для подготовки данных достаточно `python3` со стандартной библиотекой.

```bash
curl -L --fail --output data/lending-club.zip https://www.kaggle.com/api/v1/datasets/download/adarshsng/lending-club-loan-data-csv
python3 -m zipfile -t data/lending-club.zip
python3 -m zipfile -e data/lending-club.zip data/lending-club
python3 scripts/prepare_data.py data/lending-club/loan.csv --output data/lending_club_sample.csv --rows 10000 --seed 42
```
