<?php

namespace App\Services\Monolog\Logging;

use App\Services\Monolog\Handler\SuppressDuplicationHandler;
use Illuminate\Config\Repository;
use Illuminate\Log\Logger;

class SuppressDuplicationTap
{

    public function __construct(private readonly Repository $config)
    {
    }

    public function __invoke(Logger $logger): void
    {
        /** @var \Monolog\Logger $monolog */
        $monolog = $logger->getLogger();

        $handlers = $monolog->getHandlers();
        $deduplicated = new SuppressDuplicationHandler($handlers);

        $interval = $this->config->get("logging.channels.{$monolog->getName()}.suppress_duplication_interval")
            ?? $this->config->get('logging.suppress_duplication_interval');
        if (!is_null($interval)) {
            $deduplicated->setInterval($interval);
        }

        $monolog->setHandlers([$deduplicated]);
    }
}
