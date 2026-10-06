# Technical Specification: Todo List Sharing

## 1. Overview & Objective
- **Feature Summary**: Enables users to share their entire Todo list with other registered users, granting them either read-only (`viewer`) or read-write (`editor`) permissions. Owners retain full control and can revoke access or change permissions at any time.
- **Problem Statement**: Currently, Todos are strictly isolated to individual users. To support collaboration (e.g., family tasks, small team projects), users need a secure and manageable way to expose their Todo lists to trusted peers.
- **Target Audience / Roles**:
  - **Owner**: The creator of the Todo list.
  - **Viewer**: A user granted read-only access to the Owner's list.
  - **Editor**: A user granted read-write access (ability to create, update, delete Todos) on the Owner's list.

---

## 2. User Stories & Acceptance Criteria

### User Story 1: Share Todo List
- **As an** Owner,
- **I want to** share my Todo list with another user via their email address and assign a permission level (`viewer` or `editor`),
- **So that** we can collaborate on my tasks.
- **Acceptance Criteria**:
  - [x] Input must be a valid, registered user's email.
  - [x] Must fail gracefully (404/400) if the email is not registered.
  - [x] Must not allow sharing with oneself.
  - [x] Must not allow duplicate sharing (sharing to a user who already has access).

### User Story 2: Access Shared Todos
- **As a** Viewer or Editor,
- **I want to** view a combined or separate list of Todos that have been shared with me,
- **So that** I can see what I need to collaborate on.
- **Acceptance Criteria**:
  - [x] Can fetch a list of users who shared their lists with me.
  - [x] Can fetch the Todos of a specific owner I have access to.
  - [x] Viewers attempting to mutate (create/update/delete) shared Todos must receive a `403 Forbidden` error.

### User Story 3: Modify or Revoke Access
- **As an** Owner,
- **I want to** change a user's permission level or revoke their access completely,
- **So that** I maintain full control over my data privacy.
- **Acceptance Criteria**:
  - [x] Changing permission from `editor` to `viewer` takes immediate effect.
  - [x] Revoking access completely removes the user's ability to see the list.
  - [x] Changes must invalidate the affected user's cache immediately.

---

## 3. Scope
- **In-Scope**:
  - Sharing the *entire* Todo list with another user.
  - Two permission levels: `viewer` and `editor`.
  - Managing (updating/revoking) permissions.
  - Viewing lists shared by others.
- **Out-of-Scope**:
  - Sharing individual/specific Todo items (only full lists are shared).
  - External sharing via public link (requires login).
  - Sending email notifications or in-app push notifications when a list is shared.
  - "Co-owner" roles (ownership cannot be transferred).

---

## 4. Database Design

### New Table: `list_shares`
Stores the sharing relationships and permission levels.

| Column Name      | Data Type | Constraints                                      | Description |
|------------------|-----------|--------------------------------------------------|-------------|
| `id`             | UUID      | Primary Key, Default: `uuid4()`                  | Unique identifier for the share record. |
| `owner_id`       | UUID      | Foreign Key (`users.id`), `ON DELETE CASCADE`    | The user sharing their list. |
| `shared_with_id` | UUID      | Foreign Key (`users.id`), `ON DELETE CASCADE`    | The user receiving access. |
| `permission`     | String    | `NOT NULL`, Check: `IN ('viewer', 'editor')`     | The access level granted. |
| `created_at`     | DateTime  | `NOT NULL`, Default: `now()`                     | Timestamp of creation. |
| `updated_at`     | DateTime  | `NOT NULL`, Default: `now()`, `ON UPDATE now()`  | Timestamp of last modification. |

### Constraints & Indexes
- **Unique Constraint**: `UNIQUE(owner_id, shared_with_id)` — Prevents duplicate invitations.
- **Check Constraint**: `owner_id != shared_with_id` — Prevents self-sharing at the DB level.
- **Index**: `INDEX(shared_with_id)` — Optimizes queries fetching "lists shared with me".

---

## 5. API Contracts & Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| POST | `/api/v1/shares` | Share list with a user | Yes (Owner) |
| GET | `/api/v1/shares` | Get all users the Owner has shared their list with | Yes (Owner) |
| PUT | `/api/v1/shares/{share_id}` | Update permission level for a specific share | Yes (Owner) |
| DELETE | `/api/v1/shares/{share_id}` | Revoke access | Yes (Owner) |
| GET | `/api/v1/shared-with-me` | Get list of Owners who shared their lists with the current user | Yes (Collaborator) |
| GET | `/api/v1/shared-todos/{owner_id}` | Get Todos from a specific Owner | Yes (Collaborator) |

### Request & Response Examples

**POST `/api/v1/shares`**
- **Request Body**:
  ```json
  {
    "email": "collaborator@example.com",
    "permission": "editor" // Enum: "viewer", "editor"
  }
  ```
- **Responses**:
  - `201 Created`: Successfully shared.
  - `400 Bad Request`: Cannot share with yourself / User already has access.
  - `404 Not Found`: Email not found.

**PUT `/api/v1/shares/{share_id}`**
- **Request Body**: `{ "permission": "viewer" }`
- **Responses**: `200 OK` or `404 Not Found` (Share record doesn't exist).

---

## 6. Business Logic & Security Considerations

### Authorization & Permission Matrix
| Action on Todo | Owner | Editor | Viewer |
|----------------|-------|--------|--------|
| Read           | ✅    | ✅     | ✅     |
| Create         | ✅    | ✅     | ❌ (403)|
| Update         | ✅    | ✅     | ❌ (403)|
| Delete         | ✅    | ✅     | ❌ (403)|

*(Note: Editors modifying a Todo will act on behalf of the Owner; the `user_id` of the created Todo remains the Owner's ID).*

### Edge Cases & Race Conditions
- **Concurrent Updates**: If an Editor and an Owner update the same Todo simultaneously, the last write wins. Since we use `exclude_unset=True` for partial updates, conflicts are minimized unless editing the exact same field.
- **Revocation During Edit**: If the Owner revokes an Editor's access while the Editor is typing, the Editor's subsequent `PUT` request will return a `403 Forbidden` because authorization is checked at the moment the request hits the endpoint.
- **Chained Sharing**: A Collaborator (Viewer/Editor) cannot re-share the Owner's list. The `POST /api/v1/shares` endpoint strictly uses the `current_user.id` as the `owner_id`.

---

## 7. Caching & Invalidation Strategy

Currently, the cache pattern uses a version key: `todos:ver:{user_id}`.
When sharing is introduced, the caching strategy must account for multiple readers/writers.

- **Cache Keys for Shared Lists**:
  - `shared:todos:list:{owner_id}:{version}:{page}:{size}`
- **Invalidation Triggers**:
  - **Owner updates a Todo**: Bumps `todos:ver:{owner_id}`.
  - **Editor updates a shared Todo**: The backend must bump `todos:ver:{owner_id}` (not the editor's version key, because the data belongs to the owner).
  - **Owner Revokes Access / Changes Permission**:
    - The backend must immediately bump `todos:ver:{owner_id}` which forces all Viewers/Editors to fetch fresh data and re-evaluate permissions on the next request.
