<?php
/**
 * GET /api/v1/fuel-types
 * Returns the 5 tracked fuel types.
 */

declare(strict_types=1);

$rows = get_db()
    ->query('SELECT id, name FROM fuel_types ORDER BY id')
    ->fetchAll();

$data = array_map(
    fn($r) => ['id' => (int) $r['id'], 'name' => $r['name']],
    $rows
);

json_response($data, meta: ['count' => count($data)]);
