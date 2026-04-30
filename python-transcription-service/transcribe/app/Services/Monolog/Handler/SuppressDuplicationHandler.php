<?php

namespace App\Services\Monolog\Handler;

use Monolog\Handler\GroupHandler;

class SuppressDuplicationHandler extends GroupHandler
{

    private int $interval = 15;

    /**
     * @param int $interval Период (в секундах), в течение которого повторяющиеся записи должны подавляться после того, как данный журнал будет отправлен
     */
    public function setInterval(int $interval): static
    {
        $this->interval = max(0, $interval);
        return $this;
    }

    public function handle(array $record): bool
    {
        if ($this->interval != 0) {
            $key = self::class . ':' . md5($record['channel'] . ':' . $record['message']);
            if (!app('cache')->add($key, true, $this->interval)) {
                return true; // подавляем повтор
            }
        }

        return parent::handle($record);
    }
}
