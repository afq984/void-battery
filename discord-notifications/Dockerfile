FROM golang AS build-env
COPY . /go-src/
WORKDIR /go-src/
RUN go build -o /go-app .

FROM gcr.io/distroless/base
COPY --from=build-env /go-app /
ENTRYPOINT ["/go-app", "--v=1", "--alsologtostderr"]
