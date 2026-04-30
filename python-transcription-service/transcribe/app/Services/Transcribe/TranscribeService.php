<?php


namespace App\Services\Transcribe;


use DateTime;
use GuzzleHttp\Client as GuzzleHttpClient;
use GuzzleHttp\Exception\GuzzleException;
use GuzzleHttp\RequestOptions;
use Illuminate\Contracts\Cache\Repository;
use Illuminate\Contracts\Filesystem\FileNotFoundException as ContractsFileNotFoundException;
use Illuminate\Contracts\Filesystem\Filesystem;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Str;
use Psr\SimpleCache\InvalidArgumentException;

class TranscribeService
{
    private const CACHE_KEY_PREFIX     = 'results:';
    private const CACHE_RESULT_EXPIRED = '2 hours';
    private const CACHE_TASK_EXPIRED   = '1 day';

    /**
     * @var Filesystem
     */
    private $tmpStorage;
    /**
     * @var TranscribeProcess
     */
    private $transcribeProcess;
    /**
     * @var Repository
     */
    private $cache;
    /**
     * @var TranscribeQueueService
     */
    private $transcribeQueueService;
    /**
     * @var TranscribeMetricService
     */
    private $transcribeMetricService;

    /**
     * @param TranscribeProcess $transcribeProcess
     * @param TranscribeQueueService $transcribeQueueService
     * @param TranscribeMetricService $transcribeMetricService
     * @param Repository $cache
     * @param FilesystemManager $filesystemManager
     */
    public function __construct(TranscribeProcess $transcribeProcess,
                                TranscribeQueueService $transcribeQueueService,
                                TranscribeMetricService $transcribeMetricService,
                                Repository $cache,
                                FilesystemManager $filesystemManager)
    {
        $this->tmpStorage = $filesystemManager->disk('converter_audio_tmp');
        $this->transcribeProcess = $transcribeProcess;
        $this->cache = $cache;
        $this->transcribeQueueService = $transcribeQueueService;
        $this->transcribeMetricService = $transcribeMetricService;
    }

    /**
     * @param string $url_to_file
     * @param string $locale
     * @return array
     * @throws ContractsFileNotFoundException
     * @throws TranscribeServiceException
     */
    public function processByUrl(string $url_to_file, string $locale): array
    {
        $client = new GuzzleHttpClient([
            RequestOptions::TIMEOUT => 15,
            RequestOptions::VERIFY  => false,
        ]);

        try {
            $response = $client->get($url_to_file);
            $tmp_file_source = Str::random(5) . '_' . time() . '.mp3';
            try {
                $this->tmpStorage->put($tmp_file_source, $response->getBody());
                unset($response);

                $result = $this->transcribeProcess->transcribe(
                    $this->tmpStorage->path($tmp_file_source),
                    $locale
                );

                $this->transcribeMetricService->success();

                $this->transcribeMetricService->durationAudio(
                    $this->transcribeProcess->getLastDurationAudio()
                );

                $this->transcribeMetricService->durationProcess(
                    $this->transcribeProcess->getLastDurationProcess()
                );

                return $result;
            }
            finally {
                $this->tmpStorage->delete($tmp_file_source);
            }
        }
        catch (GuzzleException $e) {
            if ($e->getCode() == 404) {
                throw new ContractsFileNotFoundException('Не удалось скачать исходный файл.', $e->getCode());
            }
            $this->transcribeMetricService->error();
            throw new TranscribeServiceException($e->getMessage(), $e->getCode());
        }
        catch (TranscribeServiceException $e) {
            $this->transcribeMetricService->error();
            throw $e;
        }
    }

    /**
     * @param string $message
     * @param array $context
     */
    public function errorLog(string $message, array $context = [])
    {
        $logger = app('log')->channel("transcribe-errors-log");
        $logger->error($message, $context);
    }

    /**
     * @param string $source_url
     * @param string $callback_url
     * @param string $locale
     * @return string
     */
    public function addTask(string $source_url, string $callback_url, string $locale)
    {
        $id = $this->transcribeQueueService->createTranscribeJob($source_url, $callback_url, $locale);
        // Запишем ключ задания в кэш для индикации ожидания обработки
        $this->cache->put($this->makeCacheKey($id), [], new DateTime(self::CACHE_TASK_EXPIRED));
        return $id;
    }

    /**
     * @param string $id
     * @return array|null
     */
    public function getResult(string $id): ?array
    {
        try {
            return $this->cache->get($this->makeCacheKey($id), null);
        }
        catch (InvalidArgumentException $e) {
            return null;
        }
    }

    /**
     * @param string $id
     * @param array $data
     */
    public function setResult(string $id, array $data)
    {
        $this->cache->put($this->makeCacheKey($id), $data, new DateTime(self::CACHE_RESULT_EXPIRED));
    }

    /**
     * @param string $id
     */
    public function removeResult(string $id)
    {
        $this->cache->forget($this->makeCacheKey($id));
    }

    /**
     * @param string $id
     * @return string
     */
    private function makeCacheKey(string $id): string
    {
        return self::CACHE_KEY_PREFIX . $id;
    }
}
