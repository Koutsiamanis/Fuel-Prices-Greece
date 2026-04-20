<?php
/**
 * Response and input-validation helpers.
 * Every response in the API goes through json_response() or error_response()
 * so the envelope shape stays consistent.
 */

declare(strict_types=1);

/**
 * Send a JSON success response and exit.
 *
 * @param mixed $data The payload (array, object, list).
 * @param array $meta Metadata (count, unit, filters, etc).
 * @param int   $status HTTP status code.
 */
function json_response(mixed $data, array $meta = [], int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(
        ['data' => $data, 'meta' => $meta],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT
    );
    exit;
}

/**
 * Send a JSON error response and exit.
 */
function error_response(string $code, string $message, int $status = 400, array $details = []): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    $error = ['code' => $code, 'message' => $message];
    if ($details) {
        $error['details'] = $details;
    }
    echo json_encode(
        ['error' => $error, 'meta' => ['status' => $status]],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT
    );
    exit;
}

/**
 * Validate and return a positive integer query param. Aborts with 400 if invalid.
 */
function require_int(string $name): int
{
    $raw = $_GET[$name] ?? null;
    if ($raw === null || $raw === '') {
        error_response('missing_param', "Missing required parameter: $name");
    }
    if (!ctype_digit((string) $raw) || (int) $raw <= 0) {
        error_response('invalid_param', "Parameter '$name' must be a positive integer");
    }
    return (int) $raw;
}

/**
 * Validate and return a YYYY-MM-DD date string. Aborts with 400 if invalid.
 */
function require_date(string $name): string
{
    $raw = $_GET[$name] ?? null;
    if ($raw === null || $raw === '') {
        error_response('missing_param', "Missing required parameter: $name");
    }
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $raw)) {
        error_response('invalid_param', "Parameter '$name' must be in YYYY-MM-DD format");
    }
    $d = DateTime::createFromFormat('Y-m-d', $raw);
    if (!$d || $d->format('Y-m-d') !== $raw) {
        error_response('invalid_param', "Parameter '$name' is not a valid calendar date");
    }
    return $raw;
}

/**
 * Look up a single prefecture by id. Aborts with 404 if not found.
 */
function fetch_prefecture(PDO $db, int $id): array
{
    $stmt = $db->prepare('SELECT id, name FROM prefectures WHERE id = ?');
    $stmt->execute([$id]);
    $row = $stmt->fetch();
    if (!$row) {
        error_response('not_found', "Prefecture with id $id not found", 404);
    }
    return ['id' => (int) $row['id'], 'name' => $row['name']];
}

/**
 * Look up a single fuel type by id. Aborts with 404 if not found.
 */
function fetch_fuel_type(PDO $db, int $id): array
{
    $stmt = $db->prepare('SELECT id, name FROM fuel_types WHERE id = ?');
    $stmt->execute([$id]);
    $row = $stmt->fetch();
    if (!$row) {
        error_response('not_found', "Fuel type with id $id not found", 404);
    }
    return ['id' => (int) $row['id'], 'name' => $row['name']];
}
