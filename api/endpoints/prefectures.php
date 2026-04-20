<?php
/**
 * GET /api/v1/prefectures
 * Returns all 51 Greek prefectures plus the national weighted-average row.
 */

declare(strict_types=1);

$rows = get_db()
    ->query('SELECT id, name FROM prefectures ORDER BY id')
    ->fetchAll();

$data = array_map(
    fn($r) => ['id' => (int) $r['id'], 'name' => $r['name']],
    $rows
);

json_response($data, meta: ['count' => count($data)]);
