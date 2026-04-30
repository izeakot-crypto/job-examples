<?php

namespace App\Services\Monolog\Logging;

use Illuminate\Log\Logger;

class ServerLabelTap
{

    public function __construct(private readonly \App\Services\Monolog\Processor\ServerLabelProcessor $processor)
    {
    }

    public function __invoke(Logger $logger): void
    {
        /** @var \Monolog\Logger $monolog */
        $monolog = $logger->getLogger();
        $monolog->pushProcessor([$this->processor, '__invoke']);
    }
}
