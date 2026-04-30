<?php

namespace App\Providers;

use App\Services\Grafana;
use App\Services\Transcribe\Clients\VoskClient;
use App\Services\Transcribe\Clients\WhisperClient;
use App\Services\Transcribe\TranscribeClientInterface;
use App\Services\WebSocket;
use Barryvdh\LaravelIdeHelper\IdeHelperServiceProvider;
use GuzzleHttp\Client;
use GuzzleHttp\RequestOptions;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Filesystem\FilesystemServiceProvider;
use Illuminate\Support\ServiceProvider;
use Laravel\Lumen\Application;
use RuntimeException;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(FilesystemManager::class, function (Application $app) {
            return $app->loadComponent(
                'filesystems',
                FilesystemServiceProvider::class,
                'filesystem'
            );
        });

        $this->app->when(VoskClient::class)
            ->needs(WebSocket\Client::class)
            ->give(fn() => new WebSocket\Client(
                config('services.vosk.uri'),
                [
                    'timeout' => (int)config('services.vosk.connect_timeout', 5),
                    // 'logger' => $this->app->make('log')
                ])
            );

        $this->app->when(WhisperClient::class)
            ->needs(Client::class)
            ->give(fn() => new Client([
                'base_uri'                      => config('services.whisper.url'),
                RequestOptions::CONNECT_TIMEOUT => (int)config('services.whisper.connect_timeout') ?: 10,
                RequestOptions::TIMEOUT         => (int)config('services.whisper.timeout') ?: 60,
                RequestOptions::VERIFY          => false,
            ]));

        $this->app->bind(TranscribeClientInterface::class, function (Application $app) {
            $driver = (string)config('services.transcribe.client');
            $class = match ($driver) {
                'vosk'    => VoskClient::class,
                'whisper' => WhisperClient::class,
                default   => throw new RuntimeException("Unknown transcribe client: {$driver}"),
            };

            return $app->make($class);
        });

        $this->app->singleton(Grafana\Client::class, function (Application $app) {
            $app->configure('grafana');

            $host = (string)config('grafana.host');
            if (empty($host)) {
                $client = new Grafana\NullClient();
            }
            else {
                $client = new Grafana\Client(
                    $host,
                    config('grafana.port'),
                    config('grafana.namespace')
                );
            }

            return $client;
        });

        if ($this->app->environment() !== 'production') {
            $this->app->register(IdeHelperServiceProvider::class);
        }
    }
}
