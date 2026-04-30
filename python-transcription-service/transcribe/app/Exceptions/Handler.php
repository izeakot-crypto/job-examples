<?php

namespace App\Exceptions;

use GuzzleHttp\Exception\BadResponseException;
use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Contracts\Cache\Repository as Cache;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Queue\MaxAttemptsExceededException;
use Illuminate\Validation\ValidationException;
use Laravel\Lumen\Exceptions\Handler as ExceptionHandler;
use Psr\Log\LoggerInterface;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Throwable;

class Handler extends ExceptionHandler
{
    /**
     * A list of the exception types that should not be reported.
     *
     * @var array
     */
    protected $dontReport = [
        AuthorizationException::class,
        HttpException::class,
        ModelNotFoundException::class,
        ValidationException::class,
        MaxAttemptsExceededException::class,
    ];

    private const LOG_CHANNEL_NAME = 'exceptions-log';

    private ?LoggerInterface $customExceptionLogger = null;

    /**
     * @inheritDoc
     */
    public function report(Throwable $e)
    {
        $this->customExceptionLogger = null;

//        parent::report($e);

        if ($this->shouldntReport($e)) {
            return;
        }

        if (method_exists($e, 'report')) {
            if ($e->report() !== false) {
                return;
            }
        }

        $time = (int)config('logging.channels.exceptions-log.throttle_time');
        if ($time > 0) {
            $key = $e::class . ':' . $e->getFile() . ':' . $e->getLine();
            $cache = app(Cache::class);
            if (!$cache->add($key, true, $time)) {
                return;
            }
        }

        $context = $this->buildExceptionContext($e);

        $this->newLogger()->error($e->getMessage(), $context);
    }

    /**
     * @return LoggerInterface
     */
    protected function newLogger(): LoggerInterface
    {
        return $this->customExceptionLogger
            ?? app('log')->channel(self::LOG_CHANNEL_NAME);
    }

    /**
     * @param Throwable $e
     * @return array
     */
    protected function buildExceptionContext(Throwable $e): array
    {
        $data = array_merge(
            ['exception' => ''],
            $this->exceptionContext($e)
        );

        $data['exception'] = $this->getExceptionTrace($e);

        return $data;
    }

    /**
     * @param Throwable $e
     * @return array
     */
    protected function exceptionContext(Throwable $e): array
    {
        $context = [];

        if (method_exists($e, 'context')) {
            $context = $e->context();
        }

        if (($e instanceof BadResponseException) && str_contains($e->getMessage(), 'https://hooks.slack.com/services/')) {
            $json = json_decode((string)$e->getRequest()->getBody(), true);
            $context['slack_channel'] = '#' . ltrim($json['channel'] ?? '?', '#');
        }

        return $context;
    }

    /**
     * @param Throwable $e
     * @return array
     */
    private function getExceptionTrace(Throwable $e): array
    {
        $base_path = base_path() . DIRECTORY_SEPARATOR;

        $trace = [];
        foreach ($e->getTrace() as $n => $frame) {
            if (
                !isset($frame['file'])
                || str_contains($frame['file'], '/vendor/')
                || str_contains($frame['file'], '/Middleware/')
            ) {
                continue;
            }
            $file = str_replace($base_path, '', $frame['file']);
            $line = $frame['line'] ?? '?';
            $trace[$n] = "{$file}:{$line}";
        }

        $data = [
            'class' => $e::class,
            'code'  => $e->getCode(),
            'file'  => str_replace($base_path, '', $e->getFile()) . ':' . $e->getLine(),
            'trace' => $trace,
        ];

        if (($previous = $e->getPrevious()) instanceof Throwable) {
            $data['previous'] = $this->getExceptionTrace($previous);
        }

        return $data;
    }

    /**
     * Render an exception into an HTTP response.
     *
     * @inheritDoc
     */
    public function render($request, Throwable $e)
    {
        return parent::render($request, $e);
    }
}
