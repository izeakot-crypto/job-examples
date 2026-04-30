<?php

namespace App\Services\Monolog\Processor;

use Illuminate\Contracts\Config\Repository;
use Illuminate\Http\Request;
use Monolog\Processor\ProcessorInterface;

class ServerLabelProcessor implements ProcessorInterface
{

    public function __construct(private readonly Request    $request,
                                private readonly Repository $config)
    {
    }

    public function __invoke(array $record): array
    {
        $record['context'] = $record['context'] + [
                'server' => $this->config->get(
                    "app.name",
                    $this->request->server('SERVER_ADDR', 'undefined')
                )
            ];

        return $record;
    }
}
