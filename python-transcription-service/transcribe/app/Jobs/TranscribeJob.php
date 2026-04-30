<?php

namespace App\Jobs;

use App\Services\Transcribe\TranscribeService;
use App\Services\Transcribe\TranscribeServiceException;
use Illuminate\Contracts\Filesystem\FileNotFoundException;
use Illuminate\Support\Str;

class TranscribeJob extends Job
{
    private $job_id;
    /**
     * @var string
     */
    private $source_url;

//    private $callback_url;
    /**
     * @var string
     */
    private $locale = '';

    /**
     * @param string $source_url
     * @param string $callback_url
     * @param string $locale
     */
    public function __construct(string $source_url, string $callback_url, string $locale)
    {
        $this->job_id = md5(Str::random(5) . '_' . time());
        $this->source_url = $source_url;
//        $this->callback_url = $callback_url;
        $this->locale = $locale;
    }

    /**
     * @param TranscribeService $transcribeService
     * @return void
     */
    public function handle(TranscribeService $transcribeService)
    {
        try {
            $data = $transcribeService->processByUrl($this->source_url, $this->locale);
            $transcribeService->setResult($this->getJobId(), $data);
        }
        catch (FileNotFoundException $e) {
            $transcribeService->removeResult($this->getJobId());

            $transcribeService->errorLog($e->getMessage(), [
                'code'       => $e->getCode(),
                "file"       => $e->getFile(),
                "line"       => $e->getLine(),
                'source url' => $this->source_url,
                'locale'     => $this->locale,
            ]);
        }
        catch (TranscribeServiceException $e) {
            $transcribeService->errorLog($e->getMessage(), [
                'code'       => $e->getCode(),
                "file"       => $e->getFile(),
                "line"       => $e->getLine(),
                'source url' => $this->source_url,
                'locale'     => $this->locale,
            ]);

            $this->release();
        }
    }

    /**
     * @return string
     */
    public function getJobId(): string
    {
        return $this->job_id;
    }

    /**
     * Handle a job failure.
     *
     * @return void
     */
    public function failed()
    {
        $transcribeService = app(TranscribeService::class);
        $transcribeService->removeResult($this->getJobId());
    }
}
