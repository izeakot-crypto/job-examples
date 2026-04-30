<?php


namespace App\Services\Grafana;

class NullClient extends Client
{
    public function __construct()
    {
        parent::__construct('', 0, null);
    }

    /**
     * @inheritDoc
     */
    protected function send(array $data): Client
    {
        return $this;
    }
}
