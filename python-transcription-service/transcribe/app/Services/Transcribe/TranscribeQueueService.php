<?php


namespace App\Services\Transcribe;


use App\Jobs\TranscribeJob;
use Illuminate\Support\Facades\Queue;

class TranscribeQueueService
{
    private const QUEUE_NAME = 'transcribe';

    /**
     * @return string
     */
    private static function getQueueName(): string
    {
        return self::QUEUE_NAME;
    }

    /**
     * @return int
     */
    public static function getQueueSize(): int
    {
        return (int)Queue::size(self::getQueueName());
    }

    /**
     * @param string $source_url
     * @param string $callback_url
     * @param string $locale
     * @return string
     */
    public function createTranscribeJob(string $source_url, string $callback_url, string $locale): string
    {
        $job = new TranscribeJob($source_url, $callback_url, $locale);
        dispatch(
            $job->onQueue(self::getQueueName())
        );

        return $job->getJobId();
    }
}
