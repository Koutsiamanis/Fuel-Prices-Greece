<?php
/**
 * GET /api/v1/prices?prefecture_id=X&fuel_type_id=Y&from=YYYY-MM-DD&to=YYYY-MM-DD
 *
 * Returns a time series of prices for one prefecture + one fuel over a date range.
 * Data points are ordered oldest-first so chart libraries can plot them directly.
 */

declare(strict_types=1);

$prefectureId = require_int('prefecture_id');
$fuelTypeId   = require_int('fuel_type_id');
$from         = require_date('from');
$to           = require_date('to');

if ($from > $to) {
    error_response('invalid_range', "'from' must be on or before 'to'");
}

$db = get_db();

// Verify the IDs exist — gives consumers a clear 404 instead of a silent empty list.
$prefecture = fetch_prefecture($db, $prefectureId);
$fuelType   = fetch_fuel_type($db, $fuelTypeId);

$stmt = $db->prepare(
    'SELECT date, price
     FROM daily_fuel_prices
     WHERE prefecture_id = :pid
       AND fuel_type_id  = :fid
       AND date BETWEEN :from AND :to
     ORDER BY date ASC'
);
$stmt->execute([
    ':pid'  => $prefectureId,
    ':fid'  => $fuelTypeId,
    ':from' => $from,
    ':to'   => $to,
]);

$data = array_map(
    fn($r) => ['date' => $r['date'], 'price' => (float) $r['price']],
    $stmt->fetchAll()
);

json_response(
    $data,
    meta: [
        'count'      => count($data),
        'unit'       => PRICE_UNIT,
        'prefecture' => $prefecture,
        'fuel_type'  => $fuelType,
        'from'       => $from,
        'to'         => $to,
    ]
);
