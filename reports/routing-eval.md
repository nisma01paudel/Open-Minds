# E1 — routing accuracy

Mode: **two-stage** · Scenarios: **21** · answered by the open-weight model: 21/21

| Metric | Value |
|---|---|
| Case accuracy (exact `case_id`) | **38.1%** |
| Case accuracy on routable scenarios | **27.8%** |
| Asset identification | 42.9% |
| Duty/role identification | 52.4% |
| Escalation first hop correct | 27.8% |
| Abstention precision | 100.0% |
| Abstention recall | 18.8% |
| **Misroutes across road tiers** | **0** |
| Under-routes (abstained when routable) | 13 |
| Over-routes (routed when unidentifiable) | 0 |
| Numeric claims withheld by the guard | 0 |

## Per scenario

| id | expected | predicted | asset | ok |
|---|---|---|---|---|
| simaltal-01 | local-road-maintenance | local-road-maintenance | local-road | ✅ |
| simaltal-02 | strategic-road-emergency | strategic-road-emergency | strategic-road | ✅ |
| local-crack | local-road-maintenance | none | none | ❌ |
| local-blocked | local-road-emergency | local-road-emergency | local-road | ✅ |
| local-ward-drain | local-road-emergency | local-road-emergency | local-road | ✅ |
| highway-crack | strategic-road-maintenance | none | none | ❌ |
| highway-debris-slow | strategic-road-maintenance | none | none | ❌ |
| provincial-road | provincial-road-maintenance | none | none | ❌ |
| provincial-road-blocked | provincial-road-emergency | none | none | ❌ |
| river-erosion | riverbank-maintenance | riverbank-maintenance | riverbank | ✅ |
| river-debris-flow | riverbank-maintenance | none | none | ❌ |
| private-slope | private-land-maintenance | none | none | ❌ |
| private-house | private-land-maintenance | none | private-land | ❌ |
| school-slope | public-building-maintenance | none | none | ❌ |
| health-post | public-building-maintenance | none | local-road | ❌ |
| district-warning | warning-any | none | none | ❌ |
| geo-opinion | assessment-any | none | none | ❌ |
| district-coordination | coordination-district | none | none | ❌ |
| vague-slope | none | none | none | ✅ |
| vague-road | none | none | none | ✅ |
| vague-river | none | none | none | ✅ |
