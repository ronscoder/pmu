DISTRICTS_ALLOWED = [x.upper() for x in ('Bishnupur', 'Churachandpur', 'Chandel',
                                         'Imphal East', 'Imphal West', 'Senapati', 'Thoubal', 'Tamenglong', 'Ukhrul')]


DIVISIONS_ALLOWED = [x.upper() for x in (
    'Bishnupur',
    'Chandel',
    'Churachandpur',
    'Jiribam',
    'Pherzawl',
    'IED-I',
    'IED-II',
    'IED-III',
    'IED-IV',
    'Kakching',
    'Kangpokpi',
    'Senapati',
    'Noney',
    'Tamenglong',
    'Tengnoupal',
    'Thoubal',
    'Kamjong',
    'Ukhrul')]

PROGRESS_QFIELDS = [
                    'dtr_100',
                    'dtr_63',
                    'dtr_25',
                    'ht',
                    'ht_conductor',
                    'lt_3p',
                    'lt_1p',
                    'pole_ht_8m',
                    'pole_lt_8m',
                    'pole_9m',
                    ]

SURVEY_QFIELDS = PROGRESS_QFIELDS

REVIEW_QFIELDS = [
                    'dtr_100',
                    'dtr_63',
                    'dtr_25',
                    'ht',
                    'ht_conductor',
                    'lt_3p',
                    'lt_1p',
                    'pole_ht_8m',
                    'pole_lt_8m',
                    'pole_9m',
                    'pole_8m',
                    ]

DPR_INFRA_FIELDS = [
    'ht',
    'lt_3p',
    'lt_1p',
    'dtr_100',
    'dtr_63',
    'dtr_25',
]
