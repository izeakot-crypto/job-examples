<?php

namespace App\Services\Monolog\Processor;

use Illuminate\Http\Request;
use JsonException;
use Monolog\Processor\ProcessorInterface;

class RequestDataProcessor implements ProcessorInterface
{

    public function __construct(private readonly Request $request)
    {
    }

    public function __invoke(array $record): array
    {
        if (($this->request->header('Content-Type') === 'application/base64') && empty($this->request->input())) {
            $this->request->replace((array)json_decode(base64_decode($this->request->getContent()), true));
        }

        $data = $this->request->input();
        foreach ($data as $name => $val) {
            if (is_string($val)
                && (strlen($val) > 0)
                && (
                    str_contains($name, 'password')
                    || str_contains($name, 'confirm')
                    || str_contains($name, 'api_token')
                )
            ) {
                $data[$name] = '***';
            }
        }

        if ($this->request->isJson()) {
            try {
                json_decode($this->request->getContent(), true, flags: JSON_THROW_ON_ERROR);
            }
            catch (JsonException $json_e) {
                $check_content_json = json_encode(
                    [
                        'code'    => $json_e->getCode(),
                        'error'   => $json_e->getMessage(),
                        // тут повторно указываем, чтобы при кодировке увидеть пропущенные незакодированные символы
                        'content' => $this->request->getContent(),
                    ],
                    JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT
                );
                unset($json_e);
            }
        }

        $record['context'] = $record['context']
            + array_filter([
                'request data'       => $data,
                'content type'       => $this->request->header('Content-Type'),
                'content decoded'    => empty($data) && $this->request->header('Content-Type') === 'application/base64'
                    ? base64_decode((string)$this->request->getContent())
                    : null,
                'content raw'        => empty($data) ? $this->request->getContent() : null,
                'check content json' => $check_content_json ?? null,
            ]);

        return $record;
    }
}
