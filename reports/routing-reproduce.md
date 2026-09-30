# E1 — routing accuracy

Mode: **two-stage** · Scenarios: **21** · answered by the open-weight model: 21/21

| Metric | Value |
|---|---|
| Case accuracy (exact `case_id`) | **61.9%** |
| Case accuracy on routable scenarios | **55.6%** |
| Asset identification | 76.2% |
| Duty/role identification | 52.4% |
| Escalation first hop correct | 55.6% |
| Abstention precision | 100.0% |
| Abstention recall | 30.0% |
| **Misroutes across road tiers** | **0** |
| Under-routes (abstained when routable) | 7 |
| Over-routes (routed when unidentifiable) | 0 |
| Numeric claims withheld by the guard | 0 |

## Per scenario

| id | expected | predicted | asset | ok |
|---|---|---|---|---|
| simaltal-01 | local-road-maintenance | local-road-maintenance | local-road | ✅ |
| simaltal-02 | strategic-road-emergency | strategic-road-emergency | strategic-road | ✅ |
| local-crack | local-road-maintenance | local-road-maintenance | local-road | ✅ |
| local-blocked | local-road-emergency | none | local-road | ❌ |
| local-ward-drain | local-road-emergency | local-road-emergency | local-road | ✅ |
| highway-crack | strategic-road-maintenance | none | none | ❌ |
| highway-debris-slow | strategic-road-maintenance | none | none | ❌ |
| provincial-road | provincial-road-maintenance | provincial-road-maintenance | provincial-road | ✅ |
| provincial-road-blocked | provincial-road-emergency | provincial-road-emergency | provincial-road | ✅ |
| river-erosion | riverbank-maintenance | none | riverbank | ❌ |
| river-debris-flow | riverbank-maintenance | warning-any | any | ❌ |
| private-slope | private-land-maintenance | private-land-maintenance | private-land | ✅ |
| private-house | private-land-maintenance | none | private-land | ❌ |
| school-slope | public-building-maintenance | public-building-maintenance | public-building | ✅ |
| health-post | public-building-maintenance | none | public-building | ❌ |
| district-warning | warning-any | warning-any | any | ✅ |
| geo-opinion | assessment-any | assessment-any | any | ✅ |
| district-coordination | coordination-district | none | none | ❌ |
| vague-slope | none | none | none | ✅ |
| vague-road | none | none | none | ✅ |
| vague-river | none | none | riverbank | ✅ |
