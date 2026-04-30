<?php

/*
|--------------------------------------------------------------------------
| Application Routes
|--------------------------------------------------------------------------
|
| Here is where you can register all of the routes for an application.
| It is a breeze. Simply tell Lumen the URIs it should respond to
| and give it the Closure to call when that URI is requested.
|
*/

use App\Http\Middleware\AuthenticateByIpMiddleware;
use Laravel\Lumen\Routing\Router;

/** @var Router $router */

$router->group(
    [
        'middleware' => AuthenticateByIpMiddleware::class,
        'prefix'     => 'asr'
    ],
    function () use ($router) {
        $router->post('/add-task', '\App\Http\Controllers\TranscribeController@addTask');
        $router->get('/get/{id}', '\App\Http\Controllers\TranscribeController@get');
    }
);
