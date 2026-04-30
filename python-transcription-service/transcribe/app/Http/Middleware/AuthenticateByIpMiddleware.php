<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class AuthenticateByIpMiddleware
{
    /**
     * @param Request $request
     * @param Closure $next
     * @return mixed
     */
    public function handle(Request $request, Closure $next)
    {
        $ip = $request->ip();
        $ips = (array)config('auth.guard_ips');

        if (
            (($ips[0] ?? '') != '*')
            &&
            !in_array($ip, $ips)
        ) {
            return response('Нет доступа. ip: ' . $ip, Response::HTTP_FORBIDDEN);
        }

        return $next($request);
    }
}
