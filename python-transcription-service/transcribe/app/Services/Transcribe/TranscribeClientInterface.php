<?php

namespace App\Services\Transcribe;

interface TranscribeClientInterface
{
    /**
     * @param resource $f_handle
     * @param int $channel
     * @param string $locale
     * @return array
     * @throws TranscribeServiceException
     */
    public function process($f_handle, int $channel, string $locale): array;
}
