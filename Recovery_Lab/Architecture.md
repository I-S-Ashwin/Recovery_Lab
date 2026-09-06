# Recovery Lab architecture

```mermaid
flowchart TD
    A[Original workbook: read only] --> B[Canonical records and data audit]
    B --> C[Time-based training, tuning and calibration]
    C --> D[Frozen CatBoost and calibrated interval]
    B --> E[Final operational evaluation]
    D --> E
    D --> F[Local FastAPI service]
    G[Explicit policy and future-value assumptions] --> F
    F --> H[Compiled React dashboard]
    H --> I[Reviewer decision]
    F --> J[SQLite audit: keyed fingerprints and outcomes]
    K[Bundle hash manifest] --> F
    L[Review-only baseline fallback] --> F
```

The browser and Python service run on the same computer at port 8078. Model weights, calibration and policy remain frozen. The evidence view uses final holdout reports. Historical lookup continues to expose calibration cases only and labels them accordingly.

The notebook executes the same packaged calculation code in process, independently of the running app. The PowerPoint architecture slide contains editable native diagram objects. The event artwork comes from the uploaded cover template and remains an image.

The local release does not provide organizational authentication, distributed serving or a production underwriting approval. These are pilot gates documented in the executive summary and model card.
