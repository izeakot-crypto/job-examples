<?php


namespace App\Services\Transcribe;


use Illuminate\Support\Facades\Log;
use League\StatsD\Client;
use Throwable;

class TranscribeMetricService
{
    /**
     * @var Client
     */
    private $statsDClient;
    /**
     * @var string
     */
    private $server_label;

    /**
     * @param Client $statsDClient
     */
    public function __construct(Client $statsDClient)
    {
        $this->server_label = (string)config('app.server_label') ?: 'undefined';
        $this->statsDClient = $statsDClient;
    }

    /**
     *
     */
    public function success()
    {
        $this->sendMetric('success');
    }

    /**
     *
     */
    public function error()
    {
        $this->sendMetric('error');
    }

    /**
     * @param int $duration
     */
    public function durationAudio(int $duration)
    {
        try {
            $this->statsDClient->increment(
                sprintf(
                    'vosk.%s.duration.audio',
                    $this->server_label
                ),
                $duration
            );

            $this->statsDClient->timing(
                sprintf(
                    'vosk.%s.duration.audio',
                    $this->server_label
                ),
                $duration
            );
        }
        catch (Throwable $e) {
            Log::error($e);
        }
    }

    /**
     * @param int $duration
     */
    public function durationProcess(int $duration)
    {
        try {
            $this->statsDClient->increment(
                sprintf(
                    'vosk.%s.duration.process',
                    $this->server_label
                ),
                $duration
            );

            $this->statsDClient->timing(
                sprintf(
                    'vosk.%s.duration.process',
                    $this->server_label
                ),
                $duration
            );
        }
        catch (Throwable $e) {
            Log::error($e);
        }
    }

    /**
     * @param string $name
     */
    private function sendMetric(string $name)
    {
        try {
            $this->statsDClient->increment(sprintf(
                'vosk.%s.task.%s',
                $this->server_label,
                $name
            ));
        }
        catch (Throwable $e) {
            Log::error($e);
        }
    }
}
