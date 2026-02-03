# FHIR Gateway - Platform Verification Report

**Generated:** 2026-02-03T17:57:06.726765+00:00

## Summary

| Metric | Count |
|--------|-------|
| Total Platforms | 64 |
| Verified (Reachable) | 25 |
| Partial (Sandbox Only) | 12 |
| Needs Registration | 41 |
| Unreachable | 2 |

### By Type

| Type | Count |
|------|-------|
| Payers | 32 |
| EHRs | 20 |
| Sandboxes | 9 |

## Verified (Reachable)

| Platform | Type | Status | Response Time | FHIR Version | OAuth |
|----------|------|--------|---------------|--------------|-------|
| Aetna FHIR Sandbox | sandbox | 200 | 116ms | 4.0.1 | Yes |
| Anthem Blue Cross Blue Shield | payer | 200 | 195ms | 1.0.2 | No |
| Arkansas Blue Cross and Blue Shield | payer | 401 | 275ms | N/A | No |
| Blue Cross Blue Shield of Arizona | payer | 403 | 487ms | N/A | No |
| Blue Cross Blue Shield of Kansas City | payer | 200 | 218ms | 1.0.2 | No |
| Blue Cross Blue Shield of Michigan | payer | 200 | 708ms | 4.0.1 | No |
| Blue Cross Blue Shield of Minnesota | payer | 200 | 581ms | 4.0.1 | No |
| Blue Cross and Blue Shield of Kansas | payer | 200 | 257ms | 1.0.2 | No |
| Blue Cross and Blue Shield of Louisiana | payer | 200 | 210ms | 4.0.1 | Yes |
| BlueCross BlueShield of South Carolina | payer | 200 | 368ms | 4.0.1 | No |
| Capital BlueCross | payer | 200 | 163ms | 4.0.1 | No |
| Cerner | ehr | 200 | 705ms | 4.0.1 | Yes |
| Cigna | payer | 200 | 367ms | 4.0.1 | Yes |
| Epic FHIR Sandbox (Clinician Access) | sandbox | 200 | 222ms | 4.0.1 | Yes |
| Epic FHIR Sandbox (Patient Access) | sandbox | 200 | 213ms | 4.0.1 | Yes |
| Excellus BlueCross BlueShield | payer | 200 | 270ms | 4.0.0 | Yes |
| Flatiron Health | ehr | 200 | 461ms | 4.0.1 | No |
| Humana | payer | 200 | 675ms | 4.0.1 | Yes |
| Medicare | government | 200 | 1010ms | 4.0.1 | Yes |
| Netsmart | ehr | 200 | 212ms | 4.0.1 | Yes |
| Quest Diagnostics | lab | 200 | 114ms | 4.0.1 | No |
| SMART Health IT Sandbox (Clinician) | sandbox | 200 | 366ms | 4.0.0 | Yes |
| SMART Health IT Sandbox (Patient) | sandbox | 200 | 366ms | 4.0.0 | Yes |
| UnitedHealthcare | payer | 403 | 130ms | N/A | Yes |
| Wellmark Blue Cross Blue Shield | payer | 200 | 7715ms | 4.0.1 | No |

## Needs Registration

| Platform | Type | Developer Portal | Notes |
|----------|------|------------------|-------|
| AdvancedMD | ehr | https://developers.advancedmd.com/fhir/base-urls | No FHIR base URL configured - developer registration required |
| Aetna | payer | https://developerportal.aetna.com | No FHIR base URL configured - developer registration required |
| Allscripts | ehr | https://developer.veradigm.com | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of Alabama | payer | https://www.bcbsal.org/web/accessing-my-information | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of Massachusetts | payer | https://developer.bluecrossma.com/interops-fhir | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of North Dakota | payer | https://apiportal.bcbsnd.com/ | No FHIR base URL configured - developer registration required |
| Blue Cross NC | payer | https://www.bluecrossnc.com/policies-best-practices/notice-privacy-practices/api-access | No FHIR base URL configured - developer registration required |
| Blue Shield of California | payer | https://devportal-dev.blueshieldca.com/bsc/fhir-sandbox/ | No FHIR base URL configured - developer registration required |
| BlueCross BlueShield of Tennessee | payer | https://www.bcbst.com/developer-resources | No FHIR base URL configured - developer registration required |
| CareFirst BlueCross BlueShield | payer | https://developer.carefirst.com | No FHIR base URL configured - developer registration required |
| Centene Corporation | payer | https://partners.centene.com/ | No FHIR base URL configured - developer registration required |
| DrChrono | ehr | https://drchrono-fhirpresentation.everhealthsoftware.com/drchrono/basepractice/r4/Home/ApiDocumentation | No FHIR base URL configured - developer registration required |
| Dynamic Health IT | ehr | https://dynamicfhirpresentation.dynamicfhirsandbox.com/dhithealth/practiceone/r4/Home/ApiDocumentation | No FHIR base URL configured - developer registration required |
| Epic | ehr | https://fhir.epic.com | No FHIR base URL configured - developer registration required |
| Flatiron Health | ehr | https://flatiron.my.site.com/FHIR/s/ | Developer registration required |
| Florida Blue | payer | https://developer.bcbsfl.com/interop/interop-developer-portal/ | No FHIR base URL configured - developer registration required |
| Health Care Service Corporation | payer | https://interoperability.hcsc.com/s/documentation | No FHIR base URL configured - developer registration required |
| HealthIT.gov | sandbox | N/A | No FHIR base URL configured - developer registration required |
| Highmark Blue Cross Blue Shield | payer | https://cmsapiportal.hmhs.com/highmark-getting-started | No FHIR base URL configured - developer registration required |
| Horizon Blue Cross Blue Shield of New Jersey | payer | https://developer.interop.horizonblue.com/ | No FHIR base URL configured - developer registration required |
| Independence Blue Cross | payer | https://devportal.ibx.com/ | No FHIR base URL configured - developer registration required |
| InteliChart | ehr | https://fhir.intelichart.com/Help/AuthRegistration | No FHIR base URL configured - developer registration required |
| Kaiser Permanente | payer | https://developer.kp.org/ | No FHIR base URL configured - developer registration required |
| Logica Health | sandbox | N/A | No FHIR base URL configured - developer registration required |
| MEDHOST | ehr | https://developer.yourcareinteract.com | No FHIR base URL configured - developer registration required |
| MEDITECH | ehr | https://fhir.meditech.com/explorer/authorization | No FHIR base URL configured - developer registration required |
| MaximEyes | ehr | https://developers.first-insight.com/ | No FHIR base URL configured - developer registration required |
| Medicare | government | https://bluebutton.cms.gov/developers/ | Developer registration required |
| MeldRx | ehr | https://docs.meldrx.com/ | No FHIR base URL configured - developer registration required |
| Molina Healthcare | payer | https://developer.interop.molinahealthcare.com/ | No FHIR base URL configured - developer registration required |
| Netsmart | ehr | N/A | Developer registration required |
| NextGen | ehr | https://www.nextgen.com/patient-access-api | No FHIR base URL configured - developer registration required |
| Practice Fusion | ehr | https://practicefusion.com/fhir/get-started/ | No FHIR base URL configured - developer registration required |
| Premera Blue Cross | payer | https://www.premera.com/visitor/developers | No FHIR base URL configured - developer registration required |
| Qualifacts CareLogic | ehr | https://documentation.qualifacts.com/platform/carelogic/carelogic-fhir.html | No FHIR base URL configured - developer registration required |
| Qualifacts Credible | ehr | https://documentation.qualifacts.com/platform/credible/credible-fhir.html | No FHIR base URL configured - developer registration required |
| Qualifacts InSync | ehr | https://documentation.qualifacts.com/platform/insync/insync-fhir.html | No FHIR base URL configured - developer registration required |
| Quest Diagnostics | lab | N/A | Developer registration required |
| VA Health | government | https://developer.va.gov/explore/api/patient-health/docs | No FHIR base URL configured - developer registration required |
| athenahealth | ehr | https://developer.athenahealth.com | No FHIR base URL configured - developer registration required |
| eClinicalWorks | ehr | https://fhir.eclinicalworks.com/ecwopendev/documentation | No FHIR base URL configured - developer registration required |

## Other/Unreachable

| Platform | Type | URL | Error |
|----------|------|-----|-------|
| HAPI FHIR Server | sandbox | http://localhost:8080/fhir | Connection error: Cannot connect to host localhost:8080 ssl:default [Multiple exceptions: [Errno 61] Connect call failed ('127.0.0.1', 8080), [Errno 61] Connect call failed ('::1', 8080, 0, 0)] |
| Test HAPI FHIR Server | sandbox | http://localhost:8080/fhir | Connection error: Cannot connect to host localhost:8080 ssl:default [Multiple exceptions: [Errno 61] Connect call failed ('::1', 8080, 0, 0), [Errno 61] Connect call failed ('127.0.0.1', 8080)] |

## Capability Matrix

| Platform | Patient Access | Provider Dir | CRD | DTR | PAS | CDex |
|----------|---------------|--------------|-----|-----|-----|------|
| AdvancedMD | Yes | No | No | No | No | No |
| Aetna | Yes | Yes | Yes | Yes | Yes | Yes |
| Aetna FHIR Sandbox | Yes | No | No | No | No | No |
| Allscripts | Yes | No | No | No | No | No |
| Anthem Blue Cross Blue Shield | Yes | Yes | No | No | No | No |
| Arkansas Blue Cross and Blue Shield | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Alabama | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Arizona | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Kansas City | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Massachusetts | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Michigan | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of Minnesota | Yes | Yes | No | No | No | No |
| Blue Cross Blue Shield of North Dakota | Yes | Yes | No | No | No | No |
| Blue Cross NC | Yes | Yes | No | No | No | No |
| Blue Cross and Blue Shield of Kansas | Yes | Yes | No | No | No | No |
| Blue Cross and Blue Shield of Louisiana | Yes | Yes | No | No | No | No |
| Blue Shield of California | Yes | Yes | No | No | No | No |
| BlueCross BlueShield of South Carolina | Yes | Yes | No | No | No | No |
| BlueCross BlueShield of Tennessee | Yes | Yes | No | No | No | No |
| Capital BlueCross | Yes | Yes | No | No | No | No |
| CareFirst BlueCross BlueShield | Yes | Yes | No | No | No | Yes |
| Centene Corporation | Yes | Yes | No | No | No | No |
| Cerner | Yes | Yes | No | No | No | No |
| Cigna | Yes | Yes | No | No | No | No |
| DrChrono | Yes | No | No | No | No | No |
| Dynamic Health IT | Yes | No | No | No | No | No |
| Epic | Yes | Yes | No | No | No | No |
| Epic FHIR Sandbox (Clinician Access) | Yes | Yes | No | No | No | No |
| Epic FHIR Sandbox (Patient Access) | Yes | Yes | No | No | No | No |
| Excellus BlueCross BlueShield | Yes | Yes | No | No | No | No |
| Flatiron Health | Yes | No | No | No | No | No |
| Florida Blue | Yes | Yes | No | No | No | No |
| HAPI FHIR Server | Yes | Yes | No | No | No | No |
| Health Care Service Corporation | Yes | Yes | No | No | No | No |
| HealthIT.gov | Yes | No | No | No | No | No |
| Highmark Blue Cross Blue Shield | Yes | Yes | No | No | No | No |
| Horizon Blue Cross Blue Shield of New Jersey | Yes | Yes | No | No | No | No |
| Humana | Yes | Yes | No | No | No | No |
| Independence Blue Cross | Yes | Yes | No | No | No | No |
| InteliChart | Yes | No | No | No | No | No |
| Kaiser Permanente | Yes | Yes | No | No | No | No |
| Logica Health | Yes | No | No | No | No | No |
| MEDHOST | Yes | No | No | No | No | No |
| MEDITECH | Yes | No | No | No | No | No |
| MaximEyes | Yes | No | No | No | No | No |
| Medicare | Yes | No | No | No | No | No |
| MeldRx | Yes | No | No | No | No | No |
| Molina Healthcare | Yes | Yes | No | No | No | No |
| Netsmart | Yes | No | No | No | No | No |
| NextGen | Yes | No | No | No | No | No |
| Practice Fusion | Yes | No | No | No | No | No |
| Premera Blue Cross | Yes | Yes | No | No | No | No |
| Qualifacts CareLogic | Yes | No | No | No | No | No |
| Qualifacts Credible | Yes | No | No | No | No | No |
| Qualifacts InSync | Yes | No | No | No | No | No |
| Quest Diagnostics | Yes | No | No | No | No | No |
| SMART Health IT Sandbox (Clinician) | Yes | Yes | No | No | No | No |
| SMART Health IT Sandbox (Patient) | Yes | No | No | No | No | No |
| Test HAPI FHIR Server | Yes | Yes | Yes | Yes | Yes | Yes |
| UnitedHealthcare | Yes | Yes | Yes | Yes | Yes | Yes |
| VA Health | Yes | No | No | No | No | No |
| Wellmark Blue Cross Blue Shield | Yes | Yes | No | No | No | No |
| athenahealth | Yes | No | No | No | No | No |
| eClinicalWorks | Yes | No | No | No | No | No |

---
*Report generated by scripts/verify_platforms.py*