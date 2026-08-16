package dev.auspex.corehub.rest;

import dev.auspex.corehub.rest.dto.ErrorResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(TickerValidationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    ErrorResponse handleTickerValidation(TickerValidationException e) {
        return new ErrorResponse(e.getMessage(), HttpStatus.BAD_REQUEST.value());
    }

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    ErrorResponse handleGeneral(Exception e) {
        log.error("Unhandled exception", e);
        return new ErrorResponse("Internal server error", HttpStatus.INTERNAL_SERVER_ERROR.value());
    }
}
