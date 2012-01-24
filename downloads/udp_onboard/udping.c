#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <stdio.h>
#include <netinet/in.h>
#include <unistd.h>

#define PORT 5556

void Sendto()
{
   struct sockaddr_in receiver_addr;
   int sock_fd;
   char line[17] = "AT*LED=5,6,1,2\r";
   sock_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
   receiver_addr.sin_family = AF_INET;
	 if( inet_aton( "192.168.1.1",  &receiver_addr.sin_addr )== 0) {
		printf("Crap!, Init failed\n");
	  close(sock_fd);
		return;
	 }
   receiver_addr.sin_port = htons( PORT );
   sendto(sock_fd, line, 17, 0,(struct sockaddr*)&receiver_addr,sizeof(receiver_addr));
   close(sock_fd);
}

int main () {

	Sendto();

  printf("Seems to go ok at client\n");

}
