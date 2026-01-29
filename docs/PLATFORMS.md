# FHIR Gateway - Platform Directory

This document tracks the health and configuration status of all platforms.

## Architecture

All platforms use the `GenericPayerAdapter` which loads configuration dynamically from JSON files in `app/platforms/`.

```
app/
├── platforms/           # Platform configuration files
│   ├── aetna.json
│   ├── epic.json
│   └── ...
└── adapters/
    ├── base.py          # BasePayerAdapter with full implementation
    ├── generic.py       # GenericPayerAdapter (used for all platforms)
    └── registry.py      # Auto-registration from platforms/*.json
```

## Overview

| Category | Count | Percentage |
|----------|-------|------------|
| **Working (verified + URL)** | 24 | 38% |
| **Partial (URL but unverified)** | 10 | 16% |
| **Needs Registration** | 42 | 67% |
| **Unverified (no URL)** | 0 | 0% |
| **Total** | 62 | 100% |

### By Type

| Type | Count |
|------|-------|
| Payers | 32 |
| EHRs | 20 |
| Sandboxes | 7 |

---

## ✅ Working Platforms (24)

These platforms are verified and have FHIR URLs configured:

| Platform | ID | Type | FHIR Version | OAuth |
|----------|-----|------|--------------|-------|
| Anthem Blue Cross Blue Shield | `anthem` | payer | 1.0.2 | No |
| Arkansas Blue Cross and Blue Shield | `bcbsar` | payer | N/A | No |
| Blue Cross Blue Shield of Arizona | `bcbsaz` | payer | N/A | No |
| Blue Cross Blue Shield of Kansas City | `bluekc` | payer | 1.0.2 | No |
| Blue Cross Blue Shield of Michigan | `bcbsmi` | payer | 4.0.1 | No |
| Blue Cross Blue Shield of Minnesota | `bcbsmn` | payer | 4.0.1 | No |
| Blue Cross and Blue Shield of Kansas | `bcbsks` | payer | 1.0.2 | No |
| Blue Cross and Blue Shield of Louisiana | `bcbsla` | payer | 4.0.1 | Yes |
| BlueCross BlueShield of South Carolina | `bcbssc` | payer | 4.0.1 | No |
| Capital BlueCross | `capitalblue` | payer | 4.0.1 | No |
| Cigna | `cigna` | payer | 4.0.1 | Yes |
| Epic FHIR Sandbox (Clinician Access) | `epic-sandbox-clinician` | sandbox | 4.0.1 | Yes |
| Epic FHIR Sandbox (Patient Access) | `epic-sandbox-patient` | sandbox | 4.0.1 | Yes |
| Excellus BlueCross BlueShield | `excellus` | payer | 4.0.0 | Yes |
| Flatiron Health | `flatiron` | ehr | 4.0.1 | No |
| HAPI FHIR Server | `hapi-fhir` | sandbox | 4.0.1 | No |
| Humana | `humana` | payer | 4.0.1 | Yes |
| Medicare | `medicare` | government | 4.0.1 | Yes |
| Netsmart | `netsmart` | ehr | 4.0.1 | Yes |
| Quest Diagnostics | `questdiagnostics` | lab | 4.0.1 | No |
| SMART Health IT Sandbox | `smarthealthit-sandbox` | sandbox | 4.0.0 | Yes |
| Test HAPI FHIR Server | `test` | sandbox | 4.0.1 | Yes |
| UnitedHealthcare | `unitedhealthcare` | payer | N/A | Yes |
| Wellmark Blue Cross Blue Shield | `wellmark` | payer | 4.0.1 | No |

---

## ⚠️ Partial - Needs Verification (10)

These platforms have FHIR URLs configured but need verification:

| Platform | ID | Status |
|----------|-----|--------|
| Aetna | `aetna` | Has URL, needs verification |
| Blue Cross Blue Shield of North Dakota | `bcbsnd` | Has URL, needs verification |
| Blue Cross NC | `bcbsnc` | Has URL, needs verification |
| DrChrono | `drchrono` | Has URL, needs verification |
| Dynamic Health IT | `dynamichealthit` | Has URL, needs verification |
| InteliChart | `intelichart` | Has URL, needs verification |
| MEDHOST | `medhost` | Has URL, needs verification |
| MaximEyes | `maximeyes` | Has URL, needs verification |
| MeldRx | `meldrx` | Has URL, needs verification |
| eClinicalWorks | `eclinicalworks` | Has URL, needs verification |

---

## 🔧 Needs Registration (42)

These platforms require developer portal registration to obtain production FHIR URLs:

| Platform | ID | Developer Portal | Notes |
|----------|-----|------------------|-------|
| AdvancedMD | `advancedmd` | https://developers.advancedmd.com/fhir/base-urls | No FHIR base URL configured - developer registration required |
| Aetna | `aetna` | https://developerportal.aetna.com | No FHIR base URL configured - developer registration required |
| Allscripts | `allscripts` | https://developer.veradigm.com | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of Alabama | `bcbsal` | https://www.bcbsal.org/web/accessing-my-information | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of Massachusetts | `bcbsma` | https://developer.bluecrossma.com/interops-fhir | No FHIR base URL configured - developer registration required |
| Blue Cross Blue Shield of North Dakota | `bcbsnd` | https://apiportal.bcbsnd.com/ | No FHIR base URL configured - developer registration required |
| Blue Cross NC | `bcbsnc` | https://www.bluecrossnc.com/policies-best-practices/notice-privacy-practices/api-access | No FHIR base URL configured - developer registration required |
| Blue Shield of California | `blueshieldca` | https://devportal-dev.blueshieldca.com/bsc/fhir-sandbox/ | No FHIR base URL configured - developer registration required |
| BlueCross BlueShield of Tennessee | `bcbst` | https://www.bcbst.com/developer-resources | No FHIR base URL configured - developer registration required |
| CareFirst BlueCross BlueShield | `carefirst` | https://developer.carefirst.com | No FHIR base URL configured - developer registration required |
| Centene Corporation | `centene` | https://partners.centene.com/ | No FHIR base URL configured - developer registration required |
| Cerner | `cerner` | http://fhir.cerner.com/millennium/r4/ | No FHIR base URL configured - developer registration required |
| DrChrono | `drchrono` | https://drchrono-fhirpresentation.everhealthsoftware.com/drchrono/basepractice/r4/Home/ApiDocumentation | No FHIR base URL configured - developer registration required |
| Dynamic Health IT | `dynamichealthit` | https://dynamicfhirpresentation.dynamicfhirsandbox.com/dhithealth/practiceone/r4/Home/ApiDocumentation | No FHIR base URL configured - developer registration required |
| Epic | `epic` | https://fhir.epic.com | No FHIR base URL configured - developer registration required |
| Flatiron Health | `flatiron` | https://flatiron.my.site.com/FHIR/s/ | - |
| Florida Blue | `floridablue` | https://developer.bcbsfl.com/interop/interop-developer-portal/ | No FHIR base URL configured - developer registration required |
| Health Care Service Corporation | `hcsc` | https://interoperability.hcsc.com/s/documentation | No FHIR base URL configured - developer registration required |
| HealthIT.gov | `healthit` | - | No FHIR base URL configured - developer registration required |
| Highmark Blue Cross Blue Shield | `highmark` | https://cmsapiportal.hmhs.com/highmark-getting-started | No FHIR base URL configured - developer registration required |
| Horizon Blue Cross Blue Shield of New Jersey | `horizon` | https://developer.interop.horizonblue.com/ | No FHIR base URL configured - developer registration required |
| Independence Blue Cross | `ibx` | https://devportal.ibx.com/ | No FHIR base URL configured - developer registration required |
| InteliChart | `intelichart` | https://fhir.intelichart.com/Help/AuthRegistration | No FHIR base URL configured - developer registration required |
| Kaiser Permanente | `kaiser` | https://developer.kp.org/ | No FHIR base URL configured - developer registration required |
| Logica Health | `logica` | - | No FHIR base URL configured - developer registration required |
| MEDHOST | `medhost` | https://developer.yourcareinteract.com | No FHIR base URL configured - developer registration required |
| MEDITECH | `meditech` | https://fhir.meditech.com/explorer/authorization | No FHIR base URL configured - developer registration required |
| MaximEyes | `maximeyes` | https://developers.first-insight.com/ | No FHIR base URL configured - developer registration required |
| Medicare | `medicare` | https://bluebutton.cms.gov/developers/ | - |
| MeldRx | `meldrx` | https://docs.meldrx.com/ | No FHIR base URL configured - developer registration required |
| Molina Healthcare | `molina` | https://developer.interop.molinahealthcare.com/ | No FHIR base URL configured - developer registration required |
| Netsmart | `netsmart` | - | - |
| NextGen | `nextgen` | https://www.nextgen.com/patient-access-api | No FHIR base URL configured - developer registration required |
| Practice Fusion | `practicefusion` | https://practicefusion.com/fhir/get-started/ | No FHIR base URL configured - developer registration required |
| Premera Blue Cross | `premera` | https://www.premera.com/visitor/developers | No FHIR base URL configured - developer registration required |
| Qualifacts CareLogic | `qualifacts-carelogic` | https://documentation.qualifacts.com/platform/carelogic/carelogic-fhir.html | No FHIR base URL configured - developer registration required |
| Qualifacts Credible | `qualifacts-credible` | https://documentation.qualifacts.com/platform/credible/credible-fhir.html | No FHIR base URL configured - developer registration required |
| Qualifacts InSync | `qualifacts-insync` | https://documentation.qualifacts.com/platform/insync/insync-fhir.html | No FHIR base URL configured - developer registration required |
| Quest Diagnostics | `questdiagnostics` | - | - |
| VA Health | `vahealth` | https://developer.va.gov/explore/api/patient-health/docs | No FHIR base URL configured - developer registration required |
| athenahealth | `athena` | https://developer.athenahealth.com | No FHIR base URL configured - developer registration required |
| eClinicalWorks | `eclinicalworks` | https://fhir.eclinicalworks.com/ecwopendev/documentation | No FHIR base URL configured - developer registration required |

---

## Configuration Structure

Each platform is defined in a JSON file at `app/platforms/{platform_id}.json`:

```json
{
  "id": "platform_id",
  "name": "Full Platform Name",
  "display_name": "Display Name",
  "type": "payer|ehr|sandbox",
  "aliases": ["alias1", "alias2"],
  "patterns": ["pattern1"],
  "fhir_base_url": "https://api.platform.com/fhir/r4",
  "verification_status": "verified|needs_registration|unverified",
  "capabilities": {
    "patient_access": true,
    "crd": false,
    "dtr": false,
    "pas": false,
    "cdex": false
  },
  "developer_portal": "https://developer.platform.com",
  "oauth": {
    "authorize_url": "https://auth.platform.com/authorize",
    "token_url": "https://auth.platform.com/token"
  }
}
```

---

## Adding a New Platform

1. Create `app/platforms/{platform_id}.json` with platform details
2. Restart the server - the platform will be auto-registered

That's it! The `GenericPayerAdapter` handles everything dynamically.

---

*Last updated: January 2026*
