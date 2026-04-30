<?php


namespace App\Services\Transcribe\Clients;


use App\Services\Transcribe\TranscribeClientInterface;
use App\Services\Transcribe\TranscribeServiceException;
use App\Services\WebSocket\Client as WebSocketClient;
use Exception;

class VoskClient implements TranscribeClientInterface
{
    private const EOF = '{"eof" : 1}';  // Не изменять! Важен каждый символ!

    private int $fragment_size = 8000;


    public function __construct(private readonly WebSocketClient $client)
    {
    }

    /**
     * @inheritdoc
     */
    public function process($f_handle, int $channel, string $locale): array
    {
        $result = '';

        $this->client->setPath($locale);

        try {
            while (!feof($f_handle)) {
                $data = fread($f_handle, $this->fragment_size);
                $this->client->send($data, 'binary');
                $result .= $this->client->receive();
            }
            unset($data);

            $this->client->send(self::EOF);
            while ($this->client->getLastOpcode() != 'close') {
                $result .= $this->client->receive();
            }
        }
        catch (Exception $e) {
            throw new TranscribeServiceException($e->getMessage(), $e->getCode());
        }

        $result = preg_split('~}\s*{~', $result);

        $items = [];

        $last = count($result) - 1;
        foreach ($result as $key => $item) {
            if ($key > 0) {
                $item = '{' . $item;
            }
            if ($key < $last) {
                $item .= '}';
            }

            $item = json_decode($item, true);
            if (empty($item['result'])) {
                continue;
            }

            $start_time = reset($item['result'])['start'];
            $end_time = end($item['result'])['end'];

            $items[] = [
                'text'       => $item['text'],
                'channel'    => $channel,
                'start_time' => round($start_time, 2),
                'end_time'   => round($end_time, 2),
            ];
        }

        return $items;
    }
}
