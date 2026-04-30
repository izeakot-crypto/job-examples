<?php

namespace App\Http\Controllers;

use App\Services\Transcribe\TranscribeService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class TranscribeController extends Controller
{
    /**
     * Добавление задания
     *
     * Добавляет задание в очередь распознования. Возвращает id задания для последующего получения результата
     *
     * @queryParam source_url required url получения аудио файла
     * @queryParam locale язык распознавания
     * @response
     * {
     *      "id": "YOUR_AZURE_KEY"
     * }
     *
     * @param Request $request
     * @param TranscribeService $transcribeService
     * @return JsonResponse
     */
    public function addTask(Request $request, TranscribeService $transcribeService)
    {
        $source_url = (string)$request->input('source_url');
        $locale = (string)$request->input('locale');
        if (!filter_var($source_url, FILTER_VALIDATE_URL)) {
            return new JsonResponse(['error' => 'Invalid source_url.'], Response::HTTP_BAD_REQUEST);
        }

        $callback_url = '';
//        $callback_url = (string)$request->input('callback_url');
//        if (!filter_var($callback_url, FILTER_VALIDATE_URL)) {
//            return new JsonResponse(['error' => 'Invalid callback_url.'], Response::HTTP_BAD_REQUEST);
//        }

        $id = $transcribeService->addTask($source_url, $callback_url, $locale);

        return new JsonResponse([
            'id' => $id
        ]);
    }

    /**
     * Получение результата распознования
     *
     * Возвращет возвращает результат распознования, либо {"done": false}, если расопзнование еще в процессе
     *
     * @response
     * {
     *      "done": true,
     *      "createdAt": "2020-09-03 06:41:52",
     *      "items":
     *      [
     *          {
     *              "text": "вау",
     *              "channel": 1,
     *              "start_time": 4.47
     *          },
     *          ...
     *      ]
     * }
     *
     * @param string $id
     * @param TranscribeService $transcribeService
     * @return JsonResponse
     */
    public function get(string $id, TranscribeService $transcribeService)
    {
        $result = $transcribeService->getResult($id);

        if (is_null($result)) {
            return new JsonResponse(['error' => 'Operation id expired.'], Response::HTTP_NOT_FOUND);
        }

        $result = [
                'done' => !empty($result),
            ] + $result;

        return (new JsonResponse($result))->setEncodingOptions(JSON_UNESCAPED_UNICODE);
    }
}

