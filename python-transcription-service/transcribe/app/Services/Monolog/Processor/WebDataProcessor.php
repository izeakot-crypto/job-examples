<?php

namespace App\Services\Monolog\Processor;

use Illuminate\Http\Request;
use Monolog\Processor\ProcessorInterface;

class WebDataProcessor implements ProcessorInterface
{

    public function __construct(private readonly Request $request)
    {
    }

    public function __invoke(array $record): array
    {
        $data = array_filter([
            'url'       => $this->request->method() . ' ' . $this->request->url(),
            'sender ip' => $this->request->ip() ?: '0.0.0.0',
        ]);

        if (!$data) {
            return $record;
        }

        $record['context'] = $record['context'] + $data;

        return $record;
    }

}
