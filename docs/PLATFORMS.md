# Supported Platforms

FHIR Gateway supports 64 healthcare platforms including payers, EHRs, and government systems.

## Summary

| Category | Count |
|----------|-------|
| Working (verified) | 18 |
| Partial (needs verification) | 8 |
| Needs Registration | 38 |
| **Total** | 64 |

| Type | Count |
|------|-------|
| Payers | 32 |
| EHRs | 20 |
| Sandboxes | 9 |
| Government | 2 |
| Labs | 1 |

## Working Platforms (18)

| Platform | ID | Type | FHIR | OAuth |
|----------|-----|------|------|-------|
| Anthem Blue Cross Blue Shield | `anthem` | payer | N/A | No |
| Arkansas Blue Cross and Blue Shield | `bcbsar` | payer | N/A | No |
| Blue Cross Blue Shield of Arizona | `bcbsaz` | payer | N/A | No |
| Blue Cross Blue Shield of Kansas City | `bluekc` | payer | N/A | No |
| Blue Cross Blue Shield of Michigan | `bcbsmi` | payer | N/A | No |
| Blue Cross Blue Shield of Minnesota | `bcbsmn` | payer | N/A | No |
| Blue Cross and Blue Shield of Kansas | `bcbsks` | payer | N/A | No |
| Blue Cross and Blue Shield of Louisiana | `bcbsla` | payer | 4.0.1 | Yes |
| BlueCross BlueShield of South Carolina | `bcbssc` | payer | N/A | No |
| Capital BlueCross | `capitalblue` | payer | N/A | No |
| Cigna | `cigna` | payer | N/A | Yes |
| Excellus BlueCross BlueShield | `excellus` | payer | N/A | Yes |
| Humana | `humana` | payer | N/A | Yes |
| SMART Health IT Sandbox (Clinician) | `smarthealthit-sandbox-clinician` | sandbox | R4 | Yes |
| SMART Health IT Sandbox (Patient) | `smarthealthit-sandbox-patient` | sandbox | R4 | Yes |
| Test HAPI FHIR Server | `test` | sandbox | R4 | Yes |
| UnitedHealthcare | `unitedhealthcare` | payer | N/A | Yes |
| Wellmark Blue Cross Blue Shield | `wellmark` | payer | N/A | No |

## Partial - Needs Verification (8)

| Platform | ID | Type |
|----------|-----|------|
| Aetna FHIR Sandbox | `aetna-sandbox` | sandbox |
| Epic FHIR Sandbox (Clinician Access) | `epic-sandbox-clinician` | sandbox |
| Epic FHIR Sandbox (Patient Access) | `epic-sandbox-patient` | sandbox |
| Flatiron Health | `flatiron` | ehr |
| HAPI FHIR Server | `hapi-fhir` | sandbox |
| Medicare | `medicare` | government |
| Netsmart | `netsmart` | ehr |
| Quest Diagnostics | `questdiagnostics` | lab |

## Needs Registration (38)

These platforms require developer portal registration:

| Platform | ID | Developer Portal |
|----------|-----|------------------|
| AdvancedMD | `advancedmd` | https://developers.advancedmd.com/fhir/base-urls |
| Aetna | `aetna` | https://developerportal.aetna.com |
| Allscripts | `allscripts` | https://developer.veradigm.com |
| Blue Cross Blue Shield of Alabama | `bcbsal` | https://www.bcbsal.org/web/accessing-my-information |
| Blue Cross Blue Shield of Massachusetts | `bcbsma` | https://developer.bluecrossma.com/interops-fhir |
| Blue Cross Blue Shield of North Dakota | `bcbsnd` | https://apiportal.bcbsnd.com/ |
| Blue Cross NC | `bcbsnc` | https://www.bluecrossnc.com/policies-best-practices/notice-privacy-practices/api-access |
| Blue Shield of California | `blueshieldca` | https://devportal-dev.blueshieldca.com/bsc/fhir-sandbox/ |
| BlueCross BlueShield of Tennessee | `bcbst` | https://www.bcbst.com/developer-resources |
| CareFirst BlueCross BlueShield | `carefirst` | https://developer.carefirst.com |
| Centene Corporation | `centene` | https://partners.centene.com/ |
| Cerner | `cerner` | http://fhir.cerner.com/millennium/r4/ |
| DrChrono | `drchrono` | https://drchrono-fhirpresentation.everhealthsoftware.com/drchrono/basepractice/r4/Home/ApiDocumentation |
| Dynamic Health IT | `dynamichealthit` | https://dynamicfhirpresentation.dynamicfhirsandbox.com/dhithealth/practiceone/r4/Home/ApiDocumentation |
| Epic | `epic` | https://fhir.epic.com |
| Florida Blue | `floridablue` | https://developer.bcbsfl.com/interop/interop-developer-portal/ |
| Health Care Service Corporation | `hcsc` | https://interoperability.hcsc.com/s/documentation |
| HealthIT.gov | `healthit` | - |
| Highmark Blue Cross Blue Shield | `highmark` | https://cmsapiportal.hmhs.com/highmark-getting-started |
| Horizon Blue Cross Blue Shield of New Jersey | `horizon` | https://developer.interop.horizonblue.com/ |
| Independence Blue Cross | `ibx` | https://devportal.ibx.com/ |
| InteliChart | `intelichart` | https://fhir.intelichart.com/Help/AuthRegistration |
| Kaiser Permanente | `kaiser` | https://developer.kp.org/ |
| Logica Health | `logica` | - |
| MEDHOST | `medhost` | https://developer.yourcareinteract.com |
| MEDITECH | `meditech` | https://fhir.meditech.com/explorer/authorization |
| MaximEyes | `maximeyes` | https://developers.first-insight.com/ |
| MeldRx | `meldrx` | https://docs.meldrx.com/ |
| Molina Healthcare | `molina` | https://developer.interop.molinahealthcare.com/ |
| NextGen | `nextgen` | https://www.nextgen.com/patient-access-api |
| Practice Fusion | `practicefusion` | https://practicefusion.com/fhir/get-started/ |
| Premera Blue Cross | `premera` | https://www.premera.com/visitor/developers |
| Qualifacts CareLogic | `qualifacts-carelogic` | https://documentation.qualifacts.com/platform/carelogic/carelogic-fhir.html |
| Qualifacts Credible | `qualifacts-credible` | https://documentation.qualifacts.com/platform/credible/credible-fhir.html |
| Qualifacts InSync | `qualifacts-insync` | https://documentation.qualifacts.com/platform/insync/insync-fhir.html |
| VA Health | `vahealth` | https://developer.va.gov/explore/api/patient-health/docs |
| athenahealth | `athena` | https://developer.athenahealth.com |
| eClinicalWorks | `eclinicalworks` | https://fhir.eclinicalworks.com/ecwopendev/documentation |

## Adding a Platform

1. Create `app/platforms/{platform_id}.json`
2. Restart the server - auto-registered

See existing platform files for configuration examples.
