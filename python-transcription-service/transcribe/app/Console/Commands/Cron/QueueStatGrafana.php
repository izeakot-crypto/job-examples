<?php

namespace App\Console\Commands\Cron;

use App\Services\Grafana\Client;
use App\Services\Grafana\Exception\ConnectionException;
use App\Services\Transcribe\TranscribeQueueService;
use Illuminate\Console\Command;

class QueueStatGrafana extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'cron:queue_stat_grafana';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Обновление статистики очередей в графане.';

    private $metrics = [];

    /**
     * Execute the console command.
     *
     * @param Client $client
     * @return int
     * @throws ConnectionException
     */
    public function handle(Client $client)
    {
        $this->metrics['vosk.governor.queue.length'] = TranscribeQueueService::getQueueSize();

        $client->sendMetrics($this->metrics);

        return 0;
    }
}
