<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Contracts\Config\Repository as Config;
use Psr\Log\LoggerInterface;

class SendMessageToLogCommand extends Command
{
    protected $signature = 'tests:send-message-to-log
            {channel : Log channel | all}
            {message=Test : Message to log}
            {--level=emergency : emergency | alert | critical | error | warning | notice | info | debug}';

    protected $description = 'Отправляет сообщение в канал логирования.';

    public function handle(Config          $config,
                           LoggerInterface $log): int
    {
        $channel = $this->argument('channel');
        $is_all = $channel === 'all';
        $ok = false;
        foreach ($config->get('logging.channels') as $channel_name => $channel_params) {
            if (!$is_all && ($channel_name !== $channel)) {
                continue;
            }
            if ($is_all && !array_key_exists('name', $channel_params)) {
                continue;
            }
            $log->channel($channel_name)
                ->log(
                    $this->option('level'),
                    $this->argument('message')
                );

            $ok = true;
            $this->info("#{$channel_name}");
            sleep(1);
        }

        if (!$ok) {
            $this->error("Unknown channel: “{$channel}”");
        }

        return self::SUCCESS;
    }
}
