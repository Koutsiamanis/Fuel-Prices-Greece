<?php
/**
 * GET /api/v1/prices/latest
 *
 * Returns every price from the most recent bulletin date, grouped by prefecture.
 * Useful for a homepage "today's prices" overview without the client needing
 * to know the latest date in advance.
 */

declare(strict_types=1);

$db = get_db();

$latest = $db->query('SELECT MAX(date) AS d FROM daily_fuel_prices')->fetchColumn();
if (!$latest) {
    error_response('no_data', 'The database contains no price data yet', 404);
}

$stmt = $db->prepare(
    'SELECT pref.id   AS pref_id,
            pref.name AS pref_name,
            ft.name   AS fuel_name,
            p.price
     FROM daily_fuel_prices p
     JOIN prefectures pref ON pref.id = p.prefecture_id
     JOIN fuel_types  ft   ON ft.id   = p.fuel_type_id
     WHERE p.date = :d
     ORDER BY pref.id, ft.id'
);
$stmt->execute([':d' => $latest]);

// Group rows by prefecture → {fuel_name: price}
$grouped = [];
foreach ($stmt->fetchAll() as $row) {
    $pid = (int) $row['pref_id'];
    if (!isset($grouped[$pid])) {
        $grouped[$pid] = [
            'prefecture' => ['id' => $pid, 'name' => $row['pref_name']],
            'prices'     => [],
        ];
    }
    $grouped[$pid]['prices'][$row['fuel_name']] = (float) $row['price'];
}

json_response(
    [
        'date'    => $latest,
        'entries' => array_values($grouped),
    ],
    meta: [
        'count' => count($grouped),
        'unit'  => PRICE_UNIT,
    ]
);
