"""
TaskGuard - Application Constants
Error codes, configuration defaults, application metadata.
"""

APP_NAME    = "TaskGuard"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Security Portfolio Project"

# ─── file / directory names ───────────────────────────────────────────────────
DB_FILENAME     = "taskguard.db"
CONFIG_FILENAME = "taskguard.cfg"
LOG_FILENAME    = "taskguard_audit.jsonl"
EXPORT_DIR      = "exports"

# ─── crypto params ────────────────────────────────────────────────────────────
ARGON2_TIME_COST    = 3
ARGON2_MEMORY_COST  = 65536   # 64 MiB
ARGON2_PARALLELISM  = 2
ARGON2_HASH_LENGTH  = 32
ARGON2_SALT_LENGTH  = 32
AES_NONCE_LENGTH    = 12      # GCM standard

# ─── notification thresholds (seconds) ────────────────────────────────────────
DUE_SOON_THRESHOLD  = 86_400   # 24 hours
NOTIFY_POLL_INTERVAL = 30      # interactive mode poll seconds

# ─── error codes: TGS-XXXX ────────────────────────────────────────────────────
class ErrorCode:
    # General
    UNKNOWN          = "TGS-0000"

    # Database  TGS-1XXX
    DB_CONNECTION    = "TGS-1001"
    DB_QUERY         = "TGS-1002"
    DB_TRANSACTION   = "TGS-1003"
    DB_SCHEMA        = "TGS-1004"
    DB_INTEGRITY     = "TGS-1005"
    DB_NOT_FOUND     = "TGS-1006"
    DB_DUPLICATE     = "TGS-1007"
    DB_MIGRATION     = "TGS-1008"

    # Crypto  TGS-2XXX
    CRYPTO_ENCRYPT   = "TGS-2001"
    CRYPTO_DECRYPT   = "TGS-2002"
    CRYPTO_KEY_DERIVE= "TGS-2003"
    CRYPTO_INVALID   = "TGS-2004"
    CRYPTO_TAMPERED  = "TGS-2005"
    CRYPTO_STORE     = "TGS-2006"
    CRYPTO_NONCE     = "TGS-2007"

    # Task  TGS-3XXX
    TASK_NOT_FOUND   = "TGS-3001"
    TASK_VALIDATION  = "TGS-3002"
    TASK_DUPLICATE   = "TGS-3003"
    TASK_CONSTRAINT  = "TGS-3004"
    TASK_TRANSITION  = "TGS-3005"
    TASK_PRIORITY    = "TGS-3006"
    TASK_DATE        = "TGS-3007"
    TASK_TITLE       = "TGS-3008"

    # Search  TGS-4XXX
    SEARCH_QUERY     = "TGS-4001"
    SEARCH_TIMEOUT   = "TGS-4002"
    SEARCH_INDEX     = "TGS-4003"

    # Export  TGS-5XXX
    EXPORT_CSV       = "TGS-5001"
    EXPORT_JSON      = "TGS-5002"
    EXPORT_FILE_IO   = "TGS-5003"
    EXPORT_INVALID   = "TGS-5004"

    # Notification  TGS-6XXX
    NOTIFY_INIT      = "TGS-6001"
    NOTIFY_SEND      = "TGS-6002"

    # CLI  TGS-7XXX
    CLI_COMMAND      = "TGS-7001"
    CLI_PARSE        = "TGS-7002"
    CLI_INPUT        = "TGS-7003"
    CLI_AUTH         = "TGS-7004"

# ─── valid status transitions ─────────────────────────────────────────────────
# Maps current status → set of allowed next statuses (by name string)
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "NOT_STARTED":  {"PENDING", "ON_HOLD"},
    "PENDING":      {"ONGOING", "ON_HOLD", "NOT_COMPLETED"},
    "ONGOING":      {"COMPLETED", "ON_HOLD", "NOT_COMPLETED"},
    "ON_HOLD":      {"PENDING", "ONGOING", "NOT_COMPLETED"},
    "COMPLETED":    set(),
    "NOT_COMPLETED":{"PENDING"},
}

# ─── priority integer ordering for sorting (higher = more urgent) ─────────────
PRIORITY_ORDER: dict[str, int] = {
    "LOW":      1,
    "MEDIUM":   2,
    "HIGH":     3,
    "CRITICAL": 4,
}

# ─── display labels ──────────────────────────────────────────────────────────
STATUS_LABELS: dict[str, str] = {
    "NOT_STARTED":   "Not Started",
    "PENDING":       "Pending",
    "ONGOING":       "Ongoing",
    "ON_HOLD":       "On Hold",
    "COMPLETED":     "Completed",
    "NOT_COMPLETED": "Not Completed",
}

PRIORITY_LABELS: dict[str, str] = {
    "LOW":      "Low",
    "MEDIUM":   "Medium",
    "HIGH":     "High",
    "CRITICAL": "Critical",
}
