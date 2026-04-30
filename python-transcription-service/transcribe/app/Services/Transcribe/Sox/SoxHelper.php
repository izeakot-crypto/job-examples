<?php

namespace App\Services\Transcribe\Sox;

use Symfony\Component\Process\Exception\ProcessFailedException;
use Symfony\Component\Process\Process;

class SoxHelper
{
    private const SOX_PATH = '/usr/bin/sox';

    /**
     * @param string $full_src_path
     * @return int
     * @throws SoxException
     */
    public static function getDuration(string $full_src_path): int
    {
        $duration = self::run(['--i', '-D', $full_src_path]);
        return (int)$duration;
    }

    /**
     * @param string $full_src_path
     * @return int
     * @throws SoxException
     */
    public static function getChannelsCount(string $full_src_path): int
    {
        $channels = self::run(['--i', '-c', $full_src_path]);
        return (int)$channels;
    }

    /**
     * @param array $params
     * @return string
     * @throws SoxException
     */
    public static function run(array $params): string
    {
        $command = array_merge([self::SOX_PATH], $params);

        $process = new Process($command);

        try {
            $process->mustRun(function ($type, $buffer) use ($process) {
                $buffer = explode("\n", $buffer);
                foreach ($buffer as $line) {
                    if (preg_match('~\bFAIL\b~', $line)) {
                        $process->stop(3, SIGINT);
                        throw self::makeException($line);
                    }
                }
            });
            return $process->getOutput();
        }
        catch (ProcessFailedException) {
            throw self::makeException($process->getErrorOutput());
        }
    }

    /**
     * @param string $message
     * @return SoxException
     */
    private static function makeException(string $message): SoxException
    {
        return new SoxException($message);
    }
}
