<?php

namespace App\Services\Transcribe\Clients;

use App\Services\Transcribe\TranscribeClientInterface;
use App\Services\Transcribe\TranscribeServiceException;
use GuzzleHttp\Client;
use GuzzleHttp\Exception\GuzzleException;
use GuzzleHttp\RequestOptions;

class WhisperClient implements TranscribeClientInterface
{
    public function __construct(private readonly Client $client)
    {
    }

    /**
     * @inheritdoc
     */
    public function process($f_handle, int $channel, string $locale): array
    {
        $locale = explode('_', str_replace('-', '_', $locale))[0];

        $multipart = [
            [
                'name'     => 'model',
                'contents' => 'istupakov/parakeet-tdt-0.6b-v3-onnx',
            ],
            [
                'name'     => 'response_format',
                'contents' => 'verbose_json',
            ],
            [
                'name'     => 'pause_threshold',
                'contents' => 0.5,
            ],
            [
                'name'     => 'file',
                'contents' => $f_handle,
            ],
        ];

        $query = [
//            'response_format' => 'json',
        ];

        if ($locale) {
            $query['language'] = $locale;
        }

        $start_time = time();
        try {
            $response = $this->client->post('', [
                RequestOptions::MULTIPART => $multipart,
                //                RequestOptions::QUERY     => $query
            ]);
        }
        catch (GuzzleException $e) {
            throw new TranscribeServiceException($e->getMessage(), $e->getCode(), $e);
        }

        $duration_process = time() - $start_time;
        $result = $response->getBody()->getContents();

        $result = ((array)json_decode($result, true))['segments'] ?? [];

        $items = [];
        foreach ($result as $item) {
            $items[] = [
                'channel'    => $channel,
                'start_time' => round($item['start'], 2),
                'end_time'   => round($item['end'], 2),
                'text'       => mb_trim($item['text']),
            ];
        }

        return $items;
    }
}
