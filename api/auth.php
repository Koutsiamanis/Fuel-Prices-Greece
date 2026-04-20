<?php
/**
 * Auth hook. Currently a no-op — the API is public.
 *
 * When the professor confirms auth is needed, flip the flag below and set
 * an API_KEY environment variable in .env. No other file needs to change.
 *
 * Usage (when enabled):
 *   - Client sends header:  X-API-Key: <secret>
 *   - Request without/with-bad header gets 401.
 */

declare(strict_types=1);

const AUTH_ENABLED = false;

function authenticate(): void
{
    if (!AUTH_ENABLED) {
        return;
    }

    $expected = getenv('API_KEY') ?: '';
    $provided = $_SERVER['HTTP_X_API_KEY'] ?? '';

    if ($expected === '' || !hash_equals($expected, $provided)) {
        error_response('unauthorized', 'Missing or invalid API key', 401);
    }
}
