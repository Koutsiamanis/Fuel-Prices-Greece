<?php
/**
 * Front controller: every API request enters here.
 *
 * Responsibilities:
 *   1. Set CORS + content-type headers
 *   2. Handle OPTIONS preflight
 *   3. Resolve the route from the URL and dispatch
 *   4. Catch any uncaught exception and return a clean 500
 *
 * Route table below is the single place to add/remove endpoints.
 */

declare(strict_types=1);

require __DIR__ . '/config.php';
require __DIR__ . '/helpers.php';

// ---- CORS ---------------------------------------------------------------
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    error_response('method_not_allowed', 'Only GET requests are supported', 405);
}

// ---- Global error handler -----------------------------------------------
// Set DEBUG=1 in .env to include the exception message in the response.
// Leave unset in production — error details leak internals otherwise.
set_exception_handler(function (Throwable $e) {
    error_log($e->getMessage() . "\n" . $e->getTraceAsString());
    $details = [];
    if (getenv('DEBUG') === '1') {
        $details = [
            'exception' => get_class($e),
            'message'   => $e->getMessage(),
            'file'      => basename($e->getFile()) . ':' . $e->getLine(),
        ];
    }
    error_response('internal_error', 'An unexpected error occurred', 500, $details);
});

// ---- Resolve route ------------------------------------------------------
// The .htaccess rewrite passes the path as _route. We normalise and strip
// the version prefix so "api/v1/prices" becomes "prices".
$raw = $_GET['_route'] ?? '';
$route = trim($raw, '/');

$versionPrefix = 'v1';
if ($route === $versionPrefix) {
    $route = '';
} elseif (str_starts_with($route, $versionPrefix . '/')) {
    $route = substr($route, strlen($versionPrefix) + 1);
} elseif ($route !== '') {
    // Request hit /api/something-without-v1 — tell them about v1 instead of 404ing silently
    error_response(
        'unsupported_version',
        "Unknown or missing API version. Use /api/$versionPrefix/...",
        404
    );
}

// ---- Route table --------------------------------------------------------
// Add new endpoints here. Paths are matched exactly.
$routes = [
    ''              => 'root.php',
    'prefectures'   => 'prefectures.php',
    'fuel-types'    => 'fuel_types.php',
    'prices'        => 'prices.php',
    'prices/latest' => 'prices_latest.php',
];

if (!array_key_exists($route, $routes)) {
    error_response(
        'not_found',
        "Endpoint not found: /$versionPrefix/$route",
        404,
        ['available_routes' => array_map(fn($r) => "/$versionPrefix/$r", array_keys($routes))]
    );
}

require __DIR__ . '/endpoints/' . $routes[$route];
