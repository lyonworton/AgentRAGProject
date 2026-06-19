# Plan: Delete Collection and Ingestion Job

## Feature
Add delete functionality for knowledge base collections and ingestion jobs in the admin panel.

## Tasks

### Task 1: Add DELETE endpoint for ingestion jobs
- **File**: `app/api/v1/ingestion.py`
- Add `@router.delete("/{job_id}")` endpoint to soft-delete an ingest job
- Validate ownership (user_id match)
- Return 204 on success, 404 if not found
- Follow same pattern as other delete endpoints (auth + ownership check + 204)

### Task 2: Add `deleteIngestJob` to frontend API client
- **File**: `frontend/src/api/ingestion.ts`
- Add `deleteIngestJob(jobId: string)` function using `request()` helper with DELETE method
- Return `Promise<void>`

### Task 3: Add delete button to Ingestion Jobs admin page
- **File**: `frontend/src/routes/admin/IngestionJobs.tsx`
- Add Trash2 icon import, delete state tracking
- Only allow delete on completed/failed jobs (not running)
- Confirm dialog before delete
- Call API and refetch on success
- Show disabled state on running jobs

### Task 4: Add delete collection button to collection detail page
- **File**: `frontend/src/routes/admin/CollectionDetail.tsx`
- Add a delete collection button in the header area (next to collection name)
- Confirm before deleting
- Navigate away on success
