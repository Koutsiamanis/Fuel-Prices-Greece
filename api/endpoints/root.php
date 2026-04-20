<?php
/**
 * GET /api/v1/
 *
 * API discovery: describes available endpoints and the coverage of the dataset.
 * Acts as self-documentation for anyone landing on the API root.
 */

declare(strict_types=1);

$db = get_db();
$range = $db->query(
    'SELECT MIN(date) AS earliest, MAX(date) AS latest, COUNT(*) AS total_rows
     FROM daily_fuel_prices'
)->fetch();

$base = '/' . API_VERSION;

json_response(
    [
        'name'        => API_NAME,
        'version'     => API_VERSION,
        'description' => 'Greek daily fuel prices per prefecture, collected from the Ministry of Energy daily bulletins.',
        'endpoints'   => [
            'root'          => ['method' => 'GET', 'path' => "$base/",               'description' => 'This page'],
            'prefectures'   => ['method' => 'GET', 'path' => "$base/prefectures",    'description' => 'List all prefectures (plus the national weighted average)'],
            'fuel_types'    => ['method' => 'GET', 'path' => "$base/fuel-types",     'description' => 'List all tracked fuel types'],
            'prices'        => [
                'method' => 'GET',
                'path'   => "$base/prices",
                'description' => 'Price time series for a given prefecture + fuel + date range',
                'query_params' => [
                    'prefecture_id' => 'integer, required',
                    'fuel_type_id'  => 'integer, required',
                    'from'          => 'YYYY-MM-DD, required',
                    'to'            => 'YYYY-MM-DD, required',
                ],
            ],
            'prices_latest' => ['method' => 'GET', 'path' => "$base/prices/latest",  'description' => 'Most recent bulletin: all prices for all prefectures'],
        ],
        'data_coverage' => [
            'earliest'   => $range['earliest'] ?? null,
            'latest'     => $range['latest']   ?? null,
            'total_rows' => (int) ($range['total_rows'] ?? 0),
            'unit'       => PRICE_UNIT,
        ],
    ],
    meta: ['version' => API_VERSION]
);
