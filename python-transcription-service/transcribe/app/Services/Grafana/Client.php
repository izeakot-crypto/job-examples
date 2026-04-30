<?php

namespace App\Services\Grafana;

use App\Services\Grafana\Exception\ConnectionException;

class Client
{

    /**
     * Server protocol
     * @var string
     */
    protected $protocol = 'tcp://';
    /**
     * Server Host
     * @var string
     */
    protected $host;

    /**
     * Server Port
     * @var int
     */
    protected $port;

    /**
     * Timeout for creating the socket connection
     * @var int
     */
    protected $timeout;

    /**
     * Class namespace
     * @var string
     */
    protected $namespace = '';

    /**
     * Socket pointer for sending metrics
     * @var resource
     */
    protected $socket;

    /**
     * @param string $host
     * @param int $port
     * @param string|null $namespace
     */
    public function __construct(string $host, int $port, ?string $namespace)
    {
        $this->host = $host;
        $this->port = $port;
        if ($namespace) {
            $this->namespace = trim($namespace);
        }
        $this->timeout = ini_get('default_socket_timeout');
    }

    /**
     * @param int $timeout
     * @return Client
     */
    public function setTimeout(int $timeout): Client
    {
        $this->timeout = $timeout;
        return $this;
    }

    /**
     * @param string $name
     * @param string $value
     * @return Client
     * @throws ConnectionException
     */
    public function sendMetric(string $name, string $value): Client
    {
        $data = [
            $name => $value
        ];

        return $this->send($data);
    }

    /**
     * @param array $metrics [$name => $value, ...]
     * @return Client
     * @throws ConnectionException
     */
    public function sendMetrics(array $metrics): Client
    {
        return $this->send($metrics);
    }

    /**
     *
     */
    public function __destruct()
    {
        if ($this->socket) {
            fclose($this->socket);
            $this->socket = null;
        }
    }

    /**
     * @param array $data
     * @return Client
     * @throws ConnectionException
     */
    protected function send(array $data): Client
    {
        if (empty($data)) {
            return $this;
        }

        $socket = $this->getSocket();

        $prefix = $this->namespace ? $this->namespace . '.' : '';
        $time   = time();

        $messages = [];
        foreach ($data as $key => $value) {
            $messages[] = $prefix . $key . ' ' . $value . ' ' . $time;
        }

        $message = implode("\n", $messages) . "\n";
        @fwrite($socket, $message);
        fflush($socket);

        return $this;
    }

    /**
     * @return resource
     * @throws ConnectionException
     */
    protected function getSocket()
    {
        if (!$this->socket) {
            $this->socket = @fsockopen($this->protocol . $this->host, $this->port, $errno, $errstr, $this->timeout);
            if (!$this->socket) {
                throw new ConnectionException('(' . $errno . ') ' . $errstr);
            }
        }

        return $this->socket;
    }

}
